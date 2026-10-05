import logging
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from app.models.document import Document, DocumentVersion
from app.models.processing import Page
from app.models.knowledge import Chunk, Entity, EntityMention, Fact

logger = logging.getLogger(__name__)

class ComparisonService:
    def __init__(self, db: Session):
        self.db = db
    
    def compare_documents(self, doc_id_a: str, doc_id_b: str) -> dict:
        """Compare two documents and return structured differences."""
        # Get latest versions
        version_a = self._get_latest_version(doc_id_a)
        version_b = self._get_latest_version(doc_id_b)
        
        if not version_a or not version_b:
            return {'error': 'One or both documents not found'}
        
        # Get pages/sections
        pages_a = self.db.query(Page).filter(Page.document_version_id == version_a.id).order_by(Page.page_number).all()
        pages_b = self.db.query(Page).filter(Page.document_version_id == version_b.id).order_by(Page.page_number).all()
        
        text_a = '\n\n'.join(p.text for p in pages_a if p.text)
        text_b = '\n\n'.join(p.text for p in pages_b if p.text)
        
        # Compare sections
        sections_a = self._extract_sections(text_a)
        sections_b = self._extract_sections(text_b)
        
        differences = []
        all_section_titles = set(list(sections_a.keys()) + list(sections_b.keys()))
        
        for title in sorted(all_section_titles):
            content_a = sections_a.get(title)
            content_b = sections_b.get(title)
            
            if content_a and not content_b:
                differences.append({'category': 'removed', 'section': title, 'content_a': content_a, 'content_b': None})
            elif content_b and not content_a:
                differences.append({'category': 'added', 'section': title, 'content_a': None, 'content_b': content_b})
            elif content_a and content_b:
                similarity = SequenceMatcher(None, content_a, content_b).ratio()
                if similarity > 0.95:
                    differences.append({'category': 'unchanged', 'section': title, 'content_a': content_a[:200], 'content_b': content_b[:200]})
                else:
                    differences.append({'category': 'modified', 'section': title, 'content_a': content_a, 'content_b': content_b})
        
        # Compare entities
        entities_a = set(self._get_entity_names(version_a.id))
        entities_b = set(self._get_entity_names(version_b.id))
        
        # Compare facts
        facts_a = self._get_facts(version_a.id)
        facts_b = self._get_facts(version_b.id)
        
        added_entities = entities_b - entities_a
        removed_entities = entities_a - entities_b
        
        summary_parts = []
        modified_count = sum(1 for d in differences if d['category'] == 'modified')
        added_count = sum(1 for d in differences if d['category'] == 'added')
        removed_count = sum(1 for d in differences if d['category'] == 'removed')
        unchanged_count = sum(1 for d in differences if d['category'] == 'unchanged')
        
        summary_parts.append(f'{modified_count} sections modified')
        summary_parts.append(f'{added_count} sections added')
        summary_parts.append(f'{removed_count} sections removed')
        summary_parts.append(f'{unchanged_count} sections unchanged')
        if added_entities:
            summary_parts.append(f'New entities: {", ".join(list(added_entities)[:5])}')
        if removed_entities:
            summary_parts.append(f'Removed entities: {", ".join(list(removed_entities)[:5])}')
        
        return {
            'document_a': doc_id_a,
            'document_b': doc_id_b,
            'differences': differences,
            'summary': '; '.join(summary_parts)
        }
    
    def _get_latest_version(self, doc_id: str):
        import uuid
        return self.db.query(DocumentVersion).filter(
            DocumentVersion.document_id == uuid.UUID(doc_id)
        ).order_by(DocumentVersion.version_number.desc()).first()
    
    def _extract_sections(self, text: str) -> dict:
        import re
        sections = {}
        current_title = 'Introduction'
        current_content = []
        for line in text.split('\n'):
            if line.strip().startswith('#'):
                if current_content:
                    sections[current_title] = '\n'.join(current_content).strip()
                current_title = re.sub(r'^#+\s*', '', line.strip())
                current_content = []
            else:
                current_content.append(line)
        if current_content:
            sections[current_title] = '\n'.join(current_content).strip()
        return sections
    
    def _get_entity_names(self, version_id) -> list[str]:
        from app.models.knowledge import Chunk
        chunk_ids = [c.id for c in self.db.query(Chunk.id).filter(Chunk.document_version_id == version_id).all()]
        if not chunk_ids:
            return []
        mentions = self.db.query(EntityMention).filter(EntityMention.chunk_id.in_(chunk_ids)).all()
        entity_ids = [m.entity_id for m in mentions]
        if not entity_ids:
            return []
        entities = self.db.query(Entity).filter(Entity.id.in_(entity_ids)).all()
        return [e.canonical_name for e in entities]
    
    def _get_facts(self, version_id) -> list[dict]:
        from app.models.knowledge import Chunk
        chunk_ids = [c.id for c in self.db.query(Chunk.id).filter(Chunk.document_version_id == version_id).all()]
        if not chunk_ids:
            return []
        facts = self.db.query(Fact).filter(Fact.chunk_id.in_(chunk_ids)).all()
        return [{'predicate': f.predicate, 'object_value': f.object_value} for f in facts]
