import logging
from typing import Optional
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

class Neo4jService:
    def __init__(self, uri: str = 'bolt://localhost:7687', user: str = 'neo4j', password: str = 'neo4jpassword'):
        self._driver = None
        self.uri = uri
        self.user = user
        self.password = password
    
    @property
    def driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self._driver
    
    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None
    
    def health_check(self) -> bool:
        try:
            with self.driver.session() as session:
                session.run('RETURN 1')
            return True
        except Exception as e:
            logger.error(f'Neo4j health check failed: {e}')
            return False
    
    def ensure_indexes(self):
        """Create indexes and constraints for performance"""
        with self.driver.session() as session:
            # Create constraints
            session.run('CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE')
            # Create indexes
            session.run('CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)')
            session.run('CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.canonical_name)')
            session.run('CREATE INDEX entity_doc IF NOT EXISTS FOR (e:Entity) ON (e.document_id)')
    
    def create_entity(self, entity_id: str, entity_type: str, canonical_name: str, 
                      normalized_name: str, document_id: str, document_version_id: str,
                      metadata: dict = None) -> dict:
        query = '''
        MERGE (e:Entity {entity_id: $entity_id})
        SET e.entity_type = $entity_type,
            e.canonical_name = $canonical_name,
            e.normalized_name = $normalized_name,
            e.document_id = $document_id,
            e.document_version_id = $document_version_id,
            e.metadata = $metadata
        RETURN e
        '''
        with self.driver.session() as session:
            result = session.run(query, entity_id=entity_id, entity_type=entity_type,
                               canonical_name=canonical_name, normalized_name=normalized_name,
                               document_id=document_id, document_version_id=document_version_id,
                               metadata=str(metadata or {}))
            return result.single()
    
    def create_relationship(self, source_entity_id: str, target_entity_id: str,
                           relationship_type: str, relationship_id: str,
                           document_id: str, document_version_id: str,
                           page_id: str = None, chunk_id: str = None,
                           confidence: float = 1.0) -> dict:
        # Use APOC-free approach - sanitize relationship type
        safe_type = relationship_type.upper().replace(' ', '_').replace('-', '_')
        query = f'''
        MATCH (s:Entity {{entity_id: $source_id}})
        MATCH (t:Entity {{entity_id: $target_id}})
        MERGE (s)-[r:{safe_type} {{relationship_id: $rel_id}}]->(t)
        SET r.document_id = $document_id,
            r.document_version_id = $document_version_id,
            r.page_id = $page_id,
            r.chunk_id = $chunk_id,
            r.confidence = $confidence
        RETURN s, r, t
        '''
        with self.driver.session() as session:
            result = session.run(query, source_id=source_entity_id, target_id=target_entity_id,
                               rel_id=relationship_id, document_id=document_id,
                               document_version_id=document_version_id,
                               page_id=page_id, chunk_id=chunk_id, confidence=confidence)
            return result.single()
    
    def batch_create_entities(self, entities: list[dict]):
        query = '''
        UNWIND $entities AS e
        MERGE (n:Entity {entity_id: e.entity_id})
        SET n.entity_type = e.entity_type,
            n.canonical_name = e.canonical_name,
            n.normalized_name = e.normalized_name,
            n.document_id = e.document_id,
            n.document_version_id = e.document_version_id
        '''
        with self.driver.session() as session:
            session.run(query, entities=entities)
    
    def find_related_entities(self, entity_id: str, max_depth: int = 2) -> list[dict]:
        query = '''
        MATCH (e:Entity {entity_id: $entity_id})-[r*1..%(depth)s]-(related:Entity)
        RETURN DISTINCT related.entity_id AS entity_id,
               related.entity_type AS entity_type,
               related.canonical_name AS name,
               length(r) AS distance
        ORDER BY distance
        LIMIT 50
        ''' % {'depth': max_depth}
        with self.driver.session() as session:
            result = session.run(query, entity_id=entity_id)
            return [dict(record) for record in result]
    
    def find_entities_by_document(self, document_id: str) -> list[dict]:
        query = '''
        MATCH (e:Entity {document_id: $document_id})
        RETURN e.entity_id AS entity_id, e.entity_type AS entity_type,
               e.canonical_name AS name, e.normalized_name AS normalized_name
        '''
        with self.driver.session() as session:
            result = session.run(query, document_id=document_id)
            return [dict(record) for record in result]
    
    def graph_search(self, query_text: str, limit: int = 20) -> list[dict]:
        """Search entities by name for retrieval"""
        cypher = '''
        MATCH (e:Entity)
        WHERE toLower(e.canonical_name) CONTAINS toLower($query)
           OR toLower(e.normalized_name) CONTAINS toLower($query)
        OPTIONAL MATCH (e)-[r]-(related:Entity)
        RETURN e.entity_id AS entity_id, e.entity_type AS entity_type,
               e.canonical_name AS name, e.document_id AS document_id,
               e.document_version_id AS document_version_id,
               collect(DISTINCT {name: related.canonical_name, type: type(r)}) AS relationships
        LIMIT $limit
        '''
        with self.driver.session() as session:
            result = session.run(cypher, query=query_text, limit=limit)
            return [dict(record) for record in result]
    
    def delete_document_data(self, document_id: str):
        """Delete all graph data for a document"""
        query = '''
        MATCH (e:Entity {document_id: $document_id})
        DETACH DELETE e
        '''
        with self.driver.session() as session:
            session.run(query, document_id=document_id)
    
    def delete_version_data(self, document_version_id: str):
        query = '''
        MATCH (e:Entity {document_version_id: $document_version_id})
        DETACH DELETE e
        '''
        with self.driver.session() as session:
            session.run(query, document_version_id=document_version_id)
    
    def get_entity_context(self, entity_ids: list[str]) -> list[dict]:
        """Get entities and their relationships for RAG context"""
        query = '''
        MATCH (e:Entity)
        WHERE e.entity_id IN $entity_ids
        OPTIONAL MATCH (e)-[r]->(related:Entity)
        RETURN e.entity_id AS entity_id, e.canonical_name AS name,
               e.entity_type AS type,
               collect({target: related.canonical_name, rel: type(r)}) AS outgoing
        '''
        with self.driver.session() as session:
            result = session.run(query, entity_ids=entity_ids)
            return [dict(record) for record in result]
