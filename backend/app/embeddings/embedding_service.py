from sentence_transformers import SentenceTransformer
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self._model = None
    
    @property
    def model(self):
        if self._model is None:
            logger.info(f'Loading embedding model: {settings.EMBEDDING_MODEL}')
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return self._model
    
    def embed(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts).tolist()

embedding_service = EmbeddingService()
