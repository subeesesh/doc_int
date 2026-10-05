"""Elasticsearch service for BM25 full-text search."""
import logging
from typing import Optional
from elasticsearch import Elasticsearch, helpers, NotFoundError

logger = logging.getLogger(__name__)

INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "text_analyzer": {
                    "type": "standard",
                    "stopwords": "_english_"
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "document_id": {"type": "keyword"},
            "document_version_id": {"type": "keyword"},
            "page_id": {"type": "keyword"},
            "page_number": {"type": "integer"},
            "chunk_index": {"type": "integer"},
            "text": {
                "type": "text",
                "analyzer": "text_analyzer",
                "fields": {
                    "keyword": {"type": "keyword", "ignore_above": 256}
                }
            },
            "chunk_strategy": {"type": "keyword"},
            "metadata": {"type": "object", "enabled": True},
            "user_id": {"type": "keyword"},
            "created_at": {"type": "date"}
        }
    }
}


class ElasticsearchService:
    """Manages Elasticsearch connection, indexing, and search operations."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        index_name: str = "document_chunks",
        password: str = "",
    ):
        self._client: Optional[Elasticsearch] = None
        self.host = host
        self.port = port
        self.index_name = index_name
        self.password = password

    @property
    def client(self) -> Elasticsearch:
        if self._client is None:
            url = f"http://{self.host}:{self.port}"
            kwargs = {"request_timeout": 3, "max_retries": 1, "retry_on_timeout": False}
            if self.password:
                kwargs["basic_auth"] = ("elastic", self.password)
            self._client = Elasticsearch(url, **kwargs)
        return self._client

    def health_check(self) -> bool:
        """Check if Elasticsearch is reachable (fast, 2s timeout, no retries)."""
        try:
            url = f"http://{self.host}:{self.port}"
            kwargs = {"request_timeout": 2, "max_retries": 0}
            if self.password:
                kwargs["basic_auth"] = ("elastic", self.password)
            fast_client = Elasticsearch(url, **kwargs)
            info = fast_client.info()
            logger.info(f"Elasticsearch connected: {info['version']['number']}")
            return True
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            return False

    def ensure_index(self) -> None:
        """Create index with mapping if it doesn't exist (idempotent)."""
        try:
            if not self.client.indices.exists(index=self.index_name):
                self.client.indices.create(
                    index=self.index_name, body=INDEX_MAPPING
                )
                logger.info(f"Created Elasticsearch index: {self.index_name}")
            else:
                logger.info(f"Elasticsearch index already exists: {self.index_name}")
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise

    def recreate_index(self) -> None:
        """Delete and recreate index."""
        try:
            if self.client.indices.exists(index=self.index_name):
                self.client.indices.delete(index=self.index_name)
                logger.info(f"Deleted index: {self.index_name}")
            self.ensure_index()
        except Exception as e:
            logger.error(f"Failed to recreate index: {e}")
            raise

    def index_document(self, doc_id: str, document: dict) -> None:
        """Index a single document."""
        self.client.index(index=self.index_name, id=doc_id, document=document)

    def bulk_index(self, documents: list[dict]) -> dict:
        """Bulk index documents. Each doc must have '_id' key."""
        actions = []
        for doc in documents:
            doc_id = doc.pop("_id", doc.get("chunk_id"))
            actions.append({
                "_index": self.index_name,
                "_id": doc_id,
                "_source": doc,
            })
        success, errors = helpers.bulk(self.client, actions, raise_on_error=False)
        if errors:
            logger.warning(f"Bulk index had {len(errors)} errors")
        return {"indexed": success, "errors": len(errors) if errors else 0}

    def delete_document(self, doc_id: str) -> None:
        """Delete a single document by ID."""
        try:
            self.client.delete(index=self.index_name, id=doc_id)
        except NotFoundError:
            pass

    def delete_by_document_id(self, document_id: str) -> int:
        """Delete all chunks for a given document_id."""
        result = self.client.delete_by_query(
            index=self.index_name,
            body={"query": {"term": {"document_id": document_id}}},
            refresh=True,
        )
        deleted = result.get("deleted", 0)
        logger.info(f"Deleted {deleted} chunks for document {document_id}")
        return deleted

    def delete_by_version_id(self, document_version_id: str) -> int:
        """Delete all chunks for a given document_version_id."""
        result = self.client.delete_by_query(
            index=self.index_name,
            body={"query": {"term": {"document_version_id": document_version_id}}},
            refresh=True,
        )
        return result.get("deleted", 0)

    def search(
        self,
        query: str,
        top_k: int = 10,
        document_ids: Optional[list[str]] = None,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """BM25 full-text search with optional filters."""
        must = [{"match": {"text": {"query": query, "operator": "or"}}}]
        filters = []

        if document_ids:
            filters.append({"terms": {"document_id": document_ids}})
        if user_id:
            filters.append({"term": {"user_id": user_id}})

        body = {
            "query": {
                "bool": {
                    "must": must,
                    "filter": filters,
                }
            },
            "size": top_k,
            "_source": True,
        }

        try:
            result = self.client.search(index=self.index_name, body=body)
            hits = []
            for hit in result["hits"]["hits"]:
                source = hit["_source"]
                source["_score"] = hit["_score"]
                source["_id"] = hit["_id"]
                hits.append(source)
            return hits
        except Exception as e:
            logger.error(f"Elasticsearch search failed: {e}")
            return []

    def filtered_search(
        self,
        query: str,
        filters: dict,
        top_k: int = 10,
    ) -> list[dict]:
        """Search with arbitrary field filters."""
        must = [{"match": {"text": {"query": query}}}]
        filter_clauses = [{"term": {k: v}} for k, v in filters.items()]

        body = {
            "query": {"bool": {"must": must, "filter": filter_clauses}},
            "size": top_k,
        }
        try:
            result = self.client.search(index=self.index_name, body=body)
            return [
                {**hit["_source"], "_score": hit["_score"], "_id": hit["_id"]}
                for hit in result["hits"]["hits"]
            ]
        except Exception as e:
            logger.error(f"Filtered search failed: {e}")
            return []

    def count(self) -> int:
        """Count documents in the index."""
        try:
            result = self.client.count(index=self.index_name)
            return result["count"]
        except Exception:
            return 0

    def refresh(self) -> None:
        """Refresh the index to make recent changes searchable."""
        self.client.indices.refresh(index=self.index_name)
