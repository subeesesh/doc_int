from app.models.knowledge import Chunk
from app.services.chunking import RecursiveChunker
from app.config.settings import settings

class ChunkService:
    def __init__(self, db_session):
        self.db = db_session
        self.chunker = RecursiveChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
    
    def create_chunks(self, document_version_id, pages) -> list[Chunk]:
        all_chunks = []
        chunk_index = 0
        for page in pages:
            text_chunks = self.chunker.chunk(page.text)
            for text in text_chunks:
                chunk = Chunk(
                    document_version_id=document_version_id,
                    page_id=page.id,
                    chunk_index=chunk_index,
                    text=text,
                    token_count=len(text.split()),
                    chunk_strategy='recursive'
                )
                self.db.add(chunk)
                all_chunks.append(chunk)
                chunk_index += 1
        self.db.commit()
        for c in all_chunks:
            self.db.refresh(c)
        return all_chunks