import logging
import uuid
import asyncio
from typing import Optional
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentVersion
from app.models.processing import Page
from app.models.knowledge import Chunk, Entity, EntityMention, Fact, Relationship
from app.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)

class AnalysisService:
    def __init__(self, db: Session):
        self.db = db
    
    def summarize_document(self, document_id: str) -> dict:
        version = self._get_latest_version(document_id)
        if not version:
            return {'error': 'Document not found'}
        
        pages = self.db.query(Page).filter(
            Page.document_version_id == version.id
        ).order_by(Page.page_number).all()
        
        full_text = '\n\n'.join(p.text for p in pages if p.text)
        
        # Try LLM summary
        llm = get_llm_provider()
        try:
            prompt = f'Provide a concise summary of this document:\n\n{full_text[:4000]}'
            loop = asyncio.new_event_loop()
            response = loop.run_until_complete(llm.generate(prompt))
            loop.close()
            summary = response.text
        except Exception as e:
            logger.warning(f'LLM summary failed: {e}')
            # Deterministic fallback
            sections = []
            for page in pages:
                if page.text:
                    first_line = page.text.strip().split('\n')[0]
                    sections.append(first_line)
            summary = 'Document sections: ' + '; '.join(sections[:10])
        
        return {
            'document_id': document_id,
            'summary': summary,
            'page_count': len(pages),
            'total_characters': len(full_text)
        }
    
    def extract_entities(self, document_id: str) -> dict:
        version = self._get_latest_version(document_id)
        if not version:
            return {'error': 'Document not found'}
        
        chunk_ids = [c.id for c in self.db.query(Chunk.id).filter(Chunk.document_version_id == version.id).all()]
        if not chunk_ids:
            return {'document_id': document_id, 'entities': []}
        
        mentions = self.db.query(EntityMention).filter(EntityMention.chunk_id.in_(chunk_ids)).all()
        entity_ids = list(set(m.entity_id for m in mentions))
        entities = self.db.query(Entity).filter(Entity.id.in_(entity_ids)).all() if entity_ids else []
        
        return {
            'document_id': document_id,
            'entities': [
                {
                    'id': str(e.id),
                    'type': e.entity_type,
                    'name': e.canonical_name,
                    'mention_count': sum(1 for m in mentions if m.entity_id == e.id)
                }
                for e in entities
            ]
        }
    
    def extract_facts(self, document_id: str) -> dict:
        version = self._get_latest_version(document_id)
        if not version:
            return {'error': 'Document not found'}
        
        chunk_ids = [c.id for c in self.db.query(Chunk.id).filter(Chunk.document_version_id == version.id).all()]
        if not chunk_ids:
            return {'document_id': document_id, 'facts': []}
        
        facts = self.db.query(Fact).filter(Fact.chunk_id.in_(chunk_ids)).all()
        entity_ids = set()
        for f in facts:
            entity_ids.add(f.subject_entity_id)
            if f.object_entity_id:
                entity_ids.add(f.object_entity_id)
        entities = {e.id: e for e in self.db.query(Entity).filter(Entity.id.in_(list(entity_ids))).all()} if entity_ids else {}
        
        return {
            'document_id': document_id,
            'facts': [
                {
                    'subject': entities[f.subject_entity_id].canonical_name if f.subject_entity_id in entities else 'Unknown',
                    'predicate': f.predicate,
                    'object_value': f.object_value,
                    'object_entity': entities[f.object_entity_id].canonical_name if f.object_entity_id and f.object_entity_id in entities else None,
                    'confidence': f.confidence
                }
                for f in facts
            ]
        }
    
    def _get_latest_version(self, document_id: str):
        return self.db.query(DocumentVersion).filter(
            DocumentVersion.document_id == uuid.UUID(document_id)
        ).order_by(DocumentVersion.version_number.desc()).first()
