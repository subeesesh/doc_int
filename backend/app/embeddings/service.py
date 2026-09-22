from sentence_transformers import SentenceTransformer

from app.config.settings import settings


class EmbeddingService:
    def __init__(self) -> None:
        self.model = SentenceTransformer(
            settings.embedding_model
        )

        dimension = self.model.get_sentence_embedding_dimension()

        if dimension != settings.embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: "
                f"model={dimension}, "
                f"configured={settings.embedding_dimension}"
            )

    def embed_text(self, text: str) -> list[float]:
        vector = self.model.encode(
            text,
            normalize_embeddings=True,
        )

        return vector.tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
        )

        return vectors.tolist()