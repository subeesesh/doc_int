import logging
import re
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.models.knowledge import Entity, EntityMention, Fact, Relationship
from app.graph.neo4j_client import Neo4jService
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Common entity patterns for rule-based extraction
ENTITY_PATTERNS = {
    'POLICY': r'(?:policy|procedure|guideline|regulation|rule|standard)\s*(?:on|for|regarding)?\s*([\w\s]+?)(?:\.|,|;|\n)',
    'AMOUNT': r'\$[\d,]+(?:\.\d{2})?|\d+\s*(?:days?|weeks?|hours?|minutes?|percent|%)',
    'ROLE': r'(?:employee|manager|supervisor|director|HR|human resources|department head|team lead)',
    'DEPARTMENT': r'(?:finance|HR|engineering|marketing|sales|operations|IT|legal)',
    'TIME_PERIOD': r'\d+\s*(?:days?|weeks?|months?|years?|hours?|business days?)',
    'REQUIREMENT': r'(?:must|shall|required to|obligated to|need to)\s+([^.]+)',
}

class KnowledgeExtractionService:
    def __init__(self, db: Session, neo4j_service: Optional[Neo4jService] = None):
        self.db = db
        self.neo4j = neo4j_service
        self._llm = None
    
    def extract_from_chunks(self, chunks: list, document_id: str, document_version_id: str) -> dict:
        """Extract entities, facts, and relationships from chunks."""
        stats = {'entities': 0, 'facts': 0, 'relationships': 0}
        
        all_entities = {}  # normalized_name -> Entity
        
        for chunk in chunks:
            try:
                extracted = self._extract_from_text(chunk.text)
                
                for ent_data in extracted.get('entities', []):
                    entity = self._get_or_create_entity(
                        entity_type=ent_data['type'],
                        canonical_name=ent_data['name'],
                        all_entities=all_entities
                    )
                    # Create mention
                    mention = EntityMention(
                        entity_id=entity.id,
                        page_id=chunk.page_id,
                        chunk_id=chunk.id,
                        mention_text=ent_data['mention'],
                        confidence=ent_data.get('confidence', 0.8)
                    )
                    self.db.add(mention)
                    stats['entities'] += 1
                
                for fact_data in extracted.get('facts', []):
                    subject = self._get_or_create_entity(
                        entity_type=fact_data.get('subject_type', 'CONCEPT'),
                        canonical_name=fact_data['subject'],
                        all_entities=all_entities
                    )
                    obj_entity = None
                    if fact_data.get('object_entity'):
                        obj_entity = self._get_or_create_entity(
                            entity_type=fact_data.get('object_type', 'VALUE'),
                            canonical_name=fact_data['object_entity'],
                            all_entities=all_entities
                        )
                    fact = Fact(
                        subject_entity_id=subject.id,
                        predicate=fact_data['predicate'],
                        object_value=fact_data.get('object_value'),
                        object_entity_id=obj_entity.id if obj_entity else None,
                        page_id=chunk.page_id,
                        chunk_id=chunk.id,
                        confidence=fact_data.get('confidence', 0.7)
                    )
                    self.db.add(fact)
                    stats['facts'] += 1
                
                for rel_data in extracted.get('relationships', []):
                    source = self._get_or_create_entity(
                        entity_type=rel_data.get('source_type', 'CONCEPT'),
                        canonical_name=rel_data['source'],
                        all_entities=all_entities
                    )
                    target = self._get_or_create_entity(
                        entity_type=rel_data.get('target_type', 'CONCEPT'),
                        canonical_name=rel_data['target'],
                        all_entities=all_entities
                    )
                    rel = Relationship(
                        source_entity_id=source.id,
                        relationship_type=rel_data['type'],
                        target_entity_id=target.id,
                        page_id=chunk.page_id,
                        chunk_id=chunk.id,
                        confidence=rel_data.get('confidence', 0.7)
                    )
                    self.db.add(rel)
                    stats['relationships'] += 1
                    
            except Exception as e:
                logger.error(f'Error extracting from chunk {chunk.id}: {e}')
                continue
        
        self.db.commit()
        
        # Index to Neo4j
        if self.neo4j:
            try:
                self._index_to_neo4j(all_entities, document_id, document_version_id)
            except Exception as e:
                logger.error(f'Neo4j indexing failed: {e}')
        
        logger.info(f'Knowledge extraction complete: {stats}')
        return stats
    
    def _extract_from_text(self, text: str) -> dict:
        """Rule-based extraction of entities, facts, relationships."""
        entities = []
        facts = []
        relationships = []
        
        text_lower = text.lower()
        
        # Extract monetary amounts
        for match in re.finditer(r'\$(\d[\d,]*(?:\.\d{2})?)', text):
            entities.append({'type': 'AMOUNT', 'name': f'${match.group(1)}', 'mention': match.group(0)})
        
        # Extract time periods
        for match in re.finditer(r'(\d+)\s*(days?|weeks?|months?|years?|hours?|business days?)', text_lower):
            name = f'{match.group(1)} {match.group(2)}'
            entities.append({'type': 'TIME_PERIOD', 'name': name, 'mention': match.group(0)})
        
        # Extract percentages
        for match in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:%|percent)', text_lower):
            entities.append({'type': 'PERCENTAGE', 'name': f'{match.group(1)}%', 'mention': match.group(0)})
        
        # Extract roles/titles
        role_patterns = [
            'employee', 'manager', 'supervisor', 'director', 'HR', 
            'department head', 'team lead', 'full-time', 'part-time',
            'contractor', 'intern'
        ]
        for role in role_patterns:
            if role.lower() in text_lower:
                entities.append({'type': 'ROLE', 'name': role.title(), 'mention': role})
        
        # Extract policy/topic names from headers
        for match in re.finditer(r'(?:^|\n)\s*#+\s*(.+)', text):
            topic = match.group(1).strip()
            if len(topic) > 3 and len(topic) < 100:
                entities.append({'type': 'TOPIC', 'name': topic, 'mention': topic})
        
        # Extract facts: "X is Y" or "X are Y" patterns
        for match in re.finditer(r'([A-Z][\w\s]{2,30})\s+(?:is|are)\s+([^.]{5,80})', text):
            facts.append({
                'subject': match.group(1).strip(),
                'predicate': 'is',
                'object_value': match.group(2).strip(),
                'confidence': 0.6
            })
        
        # Extract requirements: "must/shall/required to" patterns
        for match in re.finditer(r'([\w\s]{3,30})(?:must|shall|are required to|need to)\s+([^.]{5,100})', text_lower):
            subject = match.group(1).strip().title()
            action = match.group(2).strip()
            facts.append({
                'subject': subject,
                'subject_type': 'ROLE',
                'predicate': 'must',
                'object_value': action,
                'confidence': 0.8
            })
            # Create relationship too
            relationships.append({
                'source': subject,
                'source_type': 'ROLE',
                'type': 'HAS_REQUIREMENT',
                'target': action[:50],
                'target_type': 'REQUIREMENT',
                'confidence': 0.7
            })
        
        return {'entities': entities, 'facts': facts, 'relationships': relationships}
    
    def _get_or_create_entity(self, entity_type: str, canonical_name: str, all_entities: dict) -> Entity:
        normalized = canonical_name.lower().strip()
        key = f'{entity_type}:{normalized}'
        if key in all_entities:
            return all_entities[key]
        
        # Check DB
        existing = self.db.query(Entity).filter(
            Entity.entity_type == entity_type,
            Entity.normalized_name == normalized
        ).first()
        if existing:
            all_entities[key] = existing
            return existing
        
        entity = Entity(
            entity_type=entity_type,
            canonical_name=canonical_name.strip(),
            normalized_name=normalized
        )
        self.db.add(entity)
        self.db.flush()
        all_entities[key] = entity
        return entity
    
    def _index_to_neo4j(self, entities: dict, document_id: str, document_version_id: str):
        neo4j_entities = []
        for key, entity in entities.items():
            neo4j_entities.append({
                'entity_id': str(entity.id),
                'entity_type': entity.entity_type,
                'canonical_name': entity.canonical_name,
                'normalized_name': entity.normalized_name,
                'document_id': document_id,
                'document_version_id': document_version_id,
            })
        if neo4j_entities:
            self.neo4j.batch_create_entities(neo4j_entities)
        
        # Index relationships to Neo4j
        rels = self.db.query(Relationship).join(
            Entity, Relationship.source_entity_id == Entity.id
        ).filter(Entity.normalized_name.in_([e['normalized_name'] for e in neo4j_entities])).all()
        
        for rel in rels:
            try:
                safe_type = rel.relationship_type.upper().replace(' ', '_').replace('-', '_')
                if not safe_type.isidentifier():
                    safe_type = 'RELATED_TO'
                self.neo4j.create_relationship(
                    source_entity_id=str(rel.source_entity_id),
                    target_entity_id=str(rel.target_entity_id),
                    relationship_type=safe_type,
                    relationship_id=str(rel.id),
                    document_id=document_id,
                    document_version_id=document_version_id,
                    page_id=str(rel.page_id) if rel.page_id else None,
                    chunk_id=str(rel.chunk_id) if rel.chunk_id else None,
                    confidence=rel.confidence or 0.7
                )
            except Exception as e:
                logger.warning(f'Failed to create Neo4j relationship: {e}')
    
    def delete_document_knowledge(self, document_version_id: str):
        """Delete all extracted knowledge for a document version (for reprocessing)."""
        from app.models.knowledge import EntityMention, Fact, Relationship
        from app.models.processing import Page
        from app.models.knowledge import Chunk
        
        page_ids = [p.id for p in self.db.query(Page.id).filter(Page.document_version_id == uuid.UUID(document_version_id)).all()]
        chunk_ids = [c.id for c in self.db.query(Chunk.id).filter(Chunk.document_version_id == uuid.UUID(document_version_id)).all()]
        
        if chunk_ids:
            self.db.query(EntityMention).filter(EntityMention.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
            self.db.query(Fact).filter(Fact.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
            self.db.query(Relationship).filter(Relationship.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
        
        self.db.commit()
