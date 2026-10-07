import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.services.document_processor import DocumentProcessor
from app.services.page_extractor import PageExtractor
from app.services.page_service import PageService
from app.services.chunk_service import ChunkService
from app.services.indexing_service import IndexingService
from app.services.knowledge_extraction_service import KnowledgeExtractionService
from app.graph.neo4j_client import Neo4jService
from app.models.processing import ProcessingJob, Page
from app.models.knowledge import Chunk
from app.models.document import Document
from app.config.settings import settings

logger = logging.getLogger(__name__)

class DocumentProcessingService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.processor = DocumentProcessor()
        self.page_extractor = PageExtractor()
        self.page_service = PageService(db_session)
        self.chunk_service = ChunkService(db_session)
        self.indexing_service = IndexingService()
        self._neo4j = None
    
    @property
    def neo4j(self) -> Optional[Neo4jService]:
        if self._neo4j is None:
            try:
                self._neo4j = Neo4jService(
                    uri=settings.NEO4J_URI,
                    user=settings.NEO4J_USER,
                    password=settings.NEO4J_PASSWORD
                )
                if not self._neo4j.health_check():
                    logger.warning('Neo4j not available')
                    self._neo4j = None
            except Exception as e:
                logger.warning(f'Neo4j connection failed: {e}')
        return self._neo4j
    
    def process_by_id(self, document_id: str | uuid.UUID, user_id: str = None) -> dict:
        doc_uuid = uuid.UUID(str(document_id))
        doc = self.db.query(Document).filter(Document.id == doc_uuid).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        from app.models.document import DocumentVersion
        from app.storage.minio_client import minio_service

        version = (
            self.db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
        if not version:
            raise ValueError(f"No version found for document {document_id}")

        file_bytes = minio_service.download_file(version.storage_path)
        result = self.process_document(version, file_bytes, doc.filename, user_id=user_id or str(doc.user_id))
        doc.status = "processed"
        self.db.commit()
        result["document_id"] = str(doc.id)
        result["filename"] = doc.filename
        return result

    def process_document(self, document_version, file_bytes: bytes, filename: str, user_id: str = None) -> dict:
        document_id = str(document_version.document_id)
        version_id = str(document_version.id)
        
        # Create processing job
        job = ProcessingJob(
            document_version_id=document_version.id,
            job_type='full_processing',
            status='processing',
            started_at=datetime.now(timezone.utc)
        )
        self.db.add(job)
        self.db.commit()
        
        result = {'pages': 0, 'chunks': 0, 'indexed': {}, 'knowledge': {}}
        
        try:
            # Step 1: Delete existing data for idempotency
            self._cleanup_existing(document_version.id, document_id)
            
            # Step 2: Docling processing
            logger.info(f'Processing document: {filename}')
            doc_res = self.processor.process(file_bytes, filename)
            if isinstance(doc_res, dict):
                markdown = doc_res.get("markdown", "")
            else:
                markdown = str(doc_res)
                doc_res = {"markdown": markdown}
            result['markdown_length'] = len(markdown)
            
            # Step 3: Extract and save pages using Docling provenance
            pages = self.page_extractor.extract_pages(doc_res)
            saved_pages = self.page_service.save_pages(document_version.id, pages)
            result['pages'] = len(saved_pages)
            
            # Step 4: Create chunks
            saved_chunks = self.chunk_service.create_chunks(document_version.id, saved_pages)
            result['chunks'] = len(saved_chunks)
            
            # Step 5: Index to search engines
            try:
                self.indexing_service.ensure_indexes()
                index_stats = self.indexing_service.index_chunks(
                    chunks=saved_chunks,
                    document_id=document_id,
                    document_version_id=version_id,
                    user_id=user_id
                )
                result['indexed'] = index_stats
            except Exception as e:
                logger.error(f'Indexing failed: {e}')
                result['indexed'] = {'error': str(e)}
            
            # Step 6: Knowledge extraction
            try:
                ke_service = KnowledgeExtractionService(self.db, self.neo4j)
                ke_stats = ke_service.extract_from_chunks(
                    chunks=saved_chunks,
                    document_id=document_id,
                    document_version_id=version_id
                )
                result['knowledge'] = ke_stats
            except Exception as e:
                logger.error(f'Knowledge extraction failed: {e}')
                result['knowledge'] = {'error': str(e)}
            
            # Mark success
            job.status = 'completed'
            job.completed_at = datetime.now(timezone.utc)
            document_version.status = 'processed'
            self.db.commit()
            
            logger.info(f'Document processing complete: {result}')
            return result
            
        except Exception as e:
            logger.error(f'Document processing failed: {e}')
            job.status = 'failed'
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            document_version.status = 'failed'
            self.db.commit()
            raise
    
    def _cleanup_existing(self, version_id: uuid.UUID, document_id: str):
        """Remove existing processed data for idempotent reprocessing."""
        # Delete search indexes
        try:
            self.indexing_service.delete_version_indexes(str(version_id))
        except Exception as e:
            logger.warning(f'Index cleanup failed: {e}')
        
        # Delete Neo4j data
        if self.neo4j:
            try:
                self.neo4j.delete_version_data(str(version_id))
            except Exception as e:
                logger.warning(f'Neo4j cleanup failed: {e}')
        
        # Delete existing knowledge (mentions, facts, relationships)
        try:
            ke_service = KnowledgeExtractionService(self.db)
            ke_service.delete_document_knowledge(str(version_id))
        except Exception as e:
            logger.warning(f'Knowledge cleanup failed: {e}')
        
        # Delete existing chunks
        self.db.query(Chunk).filter(Chunk.document_version_id == version_id).delete(synchronize_session=False)
        
        # Delete existing pages
        self.db.query(Page).filter(Page.document_version_id == version_id).delete(synchronize_session=False)
        
        self.db.commit()
        logger.info(f'Cleaned up existing data for version {version_id}')