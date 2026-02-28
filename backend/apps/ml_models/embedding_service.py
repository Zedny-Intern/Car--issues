"""
Text embedding service used by the RAG vector store.

Default Docker path:
- Cohere embeddings (small image, no local model weights)

Optional local fallback:
- LangChain HuggingFace embeddings when ENABLE_LOCAL_TEXT_EMBEDDINGS=True
"""
import logging
from typing import Dict, List

from django.conf import settings

from .cohere_service import cohere_service

logger = logging.getLogger(__name__)

try:
    from langchain_huggingface import HuggingFaceEmbeddings
    LANGCHAIN_EMBEDDINGS_AVAILABLE = True
except ImportError:
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        LANGCHAIN_EMBEDDINGS_AVAILABLE = True
    except ImportError:
        HuggingFaceEmbeddings = None
        LANGCHAIN_EMBEDDINGS_AVAILABLE = False

try:
    from langchain_core.embeddings import Embeddings
except ImportError:
    class Embeddings:  # type: ignore[no-redef]
        """Fallback base class when langchain_core is unavailable."""
        pass


class CohereTextEmbeddings(Embeddings):
    """Minimal embeddings adapter compatible with LangChain vectorstores."""

    def __init__(self, output_dimension: int = 512):
        self.output_dimension = int(output_dimension)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return cohere_service.embed_texts(
            texts=texts,
            input_type=cohere_service.embed_input_type_document,
            output_dimension=self.output_dimension,
        )

    def embed_query(self, text: str) -> List[float]:
        results = cohere_service.embed_texts(
            texts=[text],
            input_type=cohere_service.embed_input_type_query,
            output_dimension=self.output_dimension,
        )
        return results[0] if results else []


class EmbeddingService:
    """
    Text embedding service with a light Cohere-first runtime.
    """

    def __init__(self):
        self._text_embeddings = None
        self.text_model_name = getattr(settings, 'TEXT_EMBEDDING_MODEL', 'embed-v4.0')
        self.text_embedding_backend = getattr(settings, 'TEXT_EMBEDDING_BACKEND', 'cohere')
        self.local_text_model_name = getattr(settings, 'LOCAL_TEXT_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        self.local_text_embeddings_enabled = bool(
            getattr(settings, 'ENABLE_LOCAL_TEXT_EMBEDDINGS', False)
        )
        self.embedding_dimension = int(getattr(settings, 'TEXT_EMBEDDING_DIMENSION', 512))

    @property
    def text_embeddings(self):
        """Lazy load the selected embedding backend."""
        if self._text_embeddings is not None:
            return self._text_embeddings

        preferred_backend = (self.text_embedding_backend or 'cohere').lower()

        if preferred_backend == 'cohere' and cohere_service.is_available:
            self._text_embeddings = CohereTextEmbeddings(
                output_dimension=self.embedding_dimension,
            )
            logger.info(
                "Using Cohere text embeddings (%s, dim=%s)",
                cohere_service.embed_model,
                self.embedding_dimension,
            )
            return self._text_embeddings

        if self.local_text_embeddings_enabled and LANGCHAIN_EMBEDDINGS_AVAILABLE:
            try:
                self._text_embeddings = HuggingFaceEmbeddings(
                    model_name=self.local_text_model_name,
                    encode_kwargs={'normalize_embeddings': True},
                )
                logger.info("Using local HuggingFace text embeddings (%s)", self.local_text_model_name)
                return self._text_embeddings
            except Exception as exc:
                logger.error("Failed to initialize local text embeddings: %s", exc)

        if preferred_backend == 'cohere' and not cohere_service.is_available:
            logger.warning("Cohere embeddings were requested but Cohere is not configured.")
        elif self.local_text_embeddings_enabled and not LANGCHAIN_EMBEDDINGS_AVAILABLE:
            logger.warning("Local text embeddings were requested but the package is not installed.")

        return None

    def get_text_embedding(self, text: str) -> List[float]:
        if self.text_embeddings is None:
            raise RuntimeError("No text embedding backend is available.")
        return self.text_embeddings.embed_query(text)

    def get_text_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        if self.text_embeddings is None:
            raise RuntimeError("No text embedding backend is available.")
        return self.text_embeddings.embed_documents(texts)

    @property
    def text_embedding_dim(self) -> int:
        return self.embedding_dimension

    @property
    def image_embedding_dim(self) -> int:
        return 0

    def get_model_info(self) -> Dict:
        backend = "none"
        if isinstance(self._text_embeddings, CohereTextEmbeddings):
            backend = "cohere"
        elif self._text_embeddings is not None:
            backend = "huggingface-local"

        return {
            "text_model": self.text_model_name,
            "text_backend": backend,
            "text_model_loaded": self._text_embeddings is not None,
            "text_embedding_dim": self.text_embedding_dim,
            "local_text_embeddings_enabled": self.local_text_embeddings_enabled,
            "local_text_model": self.local_text_model_name,
            "cohere_available": cohere_service.is_available,
            "langchain_available": LANGCHAIN_EMBEDDINGS_AVAILABLE,
            "clip_available": False,
        }


embedding_service = EmbeddingService()
