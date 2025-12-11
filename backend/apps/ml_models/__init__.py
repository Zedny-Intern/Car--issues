"""
Multi-modal RAG Pipeline for Car Diagnosis System.

This module provides:
- PDF parsing with text, image, and table extraction
- Multi-modal embeddings (SBERT for text, CLIP for images)
- FAISS vector storage with hybrid search
- Automatic document loading and indexing
- LLaVA-based multi-modal LLM integration
- RAG agent for intelligent retrieval and response generation
"""

default_app_config = 'apps.ml_models.apps.MlModelsConfig'
