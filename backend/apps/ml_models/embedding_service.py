"""
Multi-modal Embedding Service using LangChain.
Uses LangChain's HuggingFaceEmbeddings for text and CLIP for images.
"""
import os
import logging
from typing import List, Dict, Optional
import numpy as np

from django.conf import settings

logger = logging.getLogger(__name__)

# LangChain Embeddings
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
        logger.warning("LangChain HuggingFace embeddings not available")

# CLIP for image embeddings
try:
    import open_clip
    import torch
    from PIL import Image
    CLIP_AVAILABLE = True
except ImportError:
    open_clip = None
    torch = None
    Image = None
    CLIP_AVAILABLE = False


class EmbeddingService:
    """
    Multi-modal embedding service using LangChain.
    
    Text embeddings: LangChain HuggingFaceEmbeddings (all-MiniLM-L6-v2) - 384 dimensions
    Image embeddings: CLIP (ViT-B-32) - 512 dimensions
    """
    
    def __init__(self):
        """Initialize embedding models."""
        self._text_embeddings = None
        self._clip_model = None
        self._clip_preprocess = None
        self._clip_tokenizer = None
        
        self.device = "cuda" if torch and torch.cuda.is_available() else "cpu"
        
        # Model names
        self.text_model_name = getattr(settings, 'TEXT_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        self.clip_model_name = getattr(settings, 'CLIP_MODEL_NAME', 'ViT-B-32')
        self.clip_pretrained = getattr(settings, 'CLIP_PRETRAINED', 'openai')
        
        logger.info(f"Embedding service initialized. Device: {self.device}")
    
    @property
    def text_embeddings(self):
        """Lazy load LangChain HuggingFace embeddings."""
        if self._text_embeddings is None and LANGCHAIN_EMBEDDINGS_AVAILABLE:
            try:
                logger.info(f"Loading LangChain HuggingFaceEmbeddings: {self.text_model_name}")
                self._text_embeddings = HuggingFaceEmbeddings(
                    model_name=self.text_model_name,
                    model_kwargs={'device': self.device},
                    encode_kwargs={'normalize_embeddings': True}
                )
                logger.info("LangChain text embeddings loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load text embeddings: {e}")
        return self._text_embeddings
    
    def _load_clip_model(self):
        """Lazy load CLIP model for image embeddings."""
        if self._clip_model is None and CLIP_AVAILABLE:
            try:
                logger.info(f"Loading CLIP model: {self.clip_model_name}")
                self._clip_model, _, self._clip_preprocess = open_clip.create_model_and_transforms(
                    self.clip_model_name,
                    pretrained=self.clip_pretrained
                )
                self._clip_tokenizer = open_clip.get_tokenizer(self.clip_model_name)
                self._clip_model.to(self.device)
                self._clip_model.eval()
                logger.info("CLIP model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load CLIP model: {e}")
                raise
    
    def get_text_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using LangChain.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats (384 dimensions)
        """
        if not LANGCHAIN_EMBEDDINGS_AVAILABLE:
            raise RuntimeError("LangChain embeddings not available. Install: pip install langchain-huggingface")
        
        if self.text_embeddings is None:
            raise RuntimeError("Failed to initialize text embeddings")
        
        try:
            # LangChain embed_query for single text
            embedding = self.text_embeddings.embed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Error generating text embedding: {e}")
            raise
    
    def get_text_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts using LangChain.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings
        """
        if not LANGCHAIN_EMBEDDINGS_AVAILABLE or self.text_embeddings is None:
            raise RuntimeError("LangChain embeddings not available")
        
        try:
            # LangChain embed_documents for batch
            embeddings = self.text_embeddings.embed_documents(texts)
            return embeddings
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise
    
    def get_image_embedding(self, image_path: str) -> List[float]:
        """
        Generate embedding for an image using CLIP.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            List of floats (512 dimensions)
        """
        if not CLIP_AVAILABLE:
            raise RuntimeError("CLIP not available. Install: pip install open-clip-torch")
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        self._load_clip_model()
        
        try:
            image = Image.open(image_path).convert("RGB")
            image_tensor = self._clip_preprocess(image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                image_features = self._clip_model.encode_image(image_tensor)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            return image_features.cpu().numpy().flatten().tolist()
        except Exception as e:
            logger.error(f"Error generating image embedding: {e}")
            raise
    
    def get_image_embeddings_batch(self, image_paths: List[str], batch_size: int = 8) -> List[List[float]]:
        """
        Generate embeddings for multiple images.
        
        Args:
            image_paths: List of image paths
            batch_size: Batch size
            
        Returns:
            List of embeddings
        """
        if not CLIP_AVAILABLE:
            raise RuntimeError("CLIP not available")
        
        self._load_clip_model()
        
        embeddings = []
        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i + batch_size]
            batch_images = []
            
            for path in batch_paths:
                try:
                    image = Image.open(path).convert("RGB")
                    batch_images.append(self._clip_preprocess(image))
                except Exception as e:
                    logger.warning(f"Error loading image {path}: {e}")
                    batch_images.append(torch.zeros(3, 224, 224))
            
            try:
                image_tensor = torch.stack(batch_images).to(self.device)
                
                with torch.no_grad():
                    image_features = self._clip_model.encode_image(image_tensor)
                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                
                embeddings.extend(image_features.cpu().numpy().tolist())
            except Exception as e:
                logger.error(f"Error in batch image embedding: {e}")
                embeddings.extend([[0.0] * 512] * len(batch_paths))
        
        return embeddings
    
    def get_text_embedding_for_image_search(self, text: str) -> List[float]:
        """
        Generate CLIP text embedding for image search.
        
        Args:
            text: Query text
            
        Returns:
            List of floats (512 dimensions, CLIP space)
        """
        if not CLIP_AVAILABLE:
            raise RuntimeError("CLIP not available")
        
        self._load_clip_model()
        
        try:
            text_tokens = self._clip_tokenizer([text]).to(self.device)
            
            with torch.no_grad():
                text_features = self._clip_model.encode_text(text_tokens)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            
            return text_features.cpu().numpy().flatten().tolist()
        except Exception as e:
            logger.error(f"Error generating CLIP text embedding: {e}")
            raise
    
    @property
    def text_embedding_dim(self) -> int:
        """Get dimension of text embeddings."""
        return 384  # all-MiniLM-L6-v2
    
    @property
    def image_embedding_dim(self) -> int:
        """Get dimension of image embeddings."""
        return 512  # CLIP ViT-B-32
    
    def get_model_info(self) -> Dict:
        """Get information about loaded models."""
        return {
            "text_model": self.text_model_name,
            "text_backend": "LangChain HuggingFaceEmbeddings",
            "text_model_loaded": self._text_embeddings is not None,
            "text_embedding_dim": self.text_embedding_dim,
            "clip_model": self.clip_model_name,
            "clip_model_loaded": self._clip_model is not None,
            "image_embedding_dim": self.image_embedding_dim,
            "device": self.device,
            "langchain_available": LANGCHAIN_EMBEDDINGS_AVAILABLE,
            "clip_available": CLIP_AVAILABLE
        }


# Global service instance
embedding_service = EmbeddingService()
