"""
Vector Store using LangChain FAISS.
Text only.
"""
import os
import logging
from typing import List, Dict

from django.conf import settings

logger = logging.getLogger(__name__)

# LangChain FAISS
try:
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document
    LANGCHAIN_FAISS_AVAILABLE = True
except ImportError:
    FAISS = None
    Document = None
    LANGCHAIN_FAISS_AVAILABLE = False
    logger.warning("LangChain FAISS not available")


class MultimodalVectorStore:
    """
    Vector Store using LangChain FAISS for text.
    Named 'MultimodalVectorStore' for legacy compatibility, but now Text-Only.
    """
    
    def __init__(self, persist_directory: str = None, collection_name: str = "multimodal"):
        """Initialize vector store."""
        self.persist_directory = persist_directory or str(
            getattr(settings, 'RAG_FAISS_DB_DIR', 
                    settings.BASE_DIR / 'faiss_db')
        )
        self.collection_name = collection_name
        
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # Paths
        self.text_index_path = os.path.join(self.persist_directory, f"{collection_name}_text_lc")
        
        # LangChain FAISS for text (lazy loaded)
        self._text_vectorstore = None
        self._embeddings = None
        
        logger.info(f"VectorStore initialized (Text Only): {self.persist_directory}")
    
    @property
    def embeddings(self):
        """Lazy load LangChain embeddings."""
        if self._embeddings is None:
            from .embedding_service import embedding_service
            self._embeddings = embedding_service.text_embeddings
        return self._embeddings
    
    @property
    def text_vectorstore(self):
        """Lazy load LangChain FAISS vectorstore."""
        if self._text_vectorstore is None and LANGCHAIN_FAISS_AVAILABLE:
            if os.path.exists(self.text_index_path) and self.embeddings:
                try:
                    self._text_vectorstore = FAISS.load_local(
                        self.text_index_path,
                        self.embeddings,
                        allow_dangerous_deserialization=True
                    )
                    logger.info(f"Loaded LangChain FAISS from {self.text_index_path}")
                except Exception as e:
                    logger.warning(f"Could not load FAISS index: {e}")
        return self._text_vectorstore
    
    def add_text_documents(self, documents: List[Dict]) -> List[str]:
        """
        Add text documents using LangChain FAISS.
        
        Args:
            documents: List of {id, content, embedding, metadata}
            
        Returns:
            List of added document IDs
        """
        if not LANGCHAIN_FAISS_AVAILABLE or not self.embeddings:
            logger.warning("LangChain FAISS not available")
            return []
        
        # Convert to LangChain Documents
        lc_documents = []
        ids = []
        
        for doc in documents:
            content = doc.get('content', '')
            if not content:
                continue
            
            doc_id = doc.get('id') or doc.get('metadata', {}).get('chunk_id')
            if not doc_id:
                continue
            
            metadata = doc.get('metadata', {})
            metadata['doc_id'] = doc_id
            
            lc_documents.append(Document(
                page_content=content,
                metadata=metadata
            ))
            ids.append(doc_id)
        
        if not lc_documents:
            return []
        
        try:
            if self._text_vectorstore is None:
                # Create new vectorstore
                self._text_vectorstore = FAISS.from_documents(
                    lc_documents,
                    self.embeddings
                )
            else:
                # Add to existing
                self._text_vectorstore.add_documents(lc_documents)
            
            # Save
            self._text_vectorstore.save_local(self.text_index_path)
            logger.info(f"Added {len(ids)} text documents via LangChain FAISS")
            
            return ids
            
        except Exception as e:
            logger.error(f"Error adding text documents: {e}")
            return []

    # Deprecated/Empty image methods for compatibility
    def add_image_documents(self, documents: List[Dict]) -> List[str]:
        """Deprecated. No-op."""
        return []
    
    def search_text(self, query_embedding: List[float] = None, 
                    query: str = None, top_k: int = 5,
                    filter_metadata: Dict = None) -> List[Dict]:
        """
        Search text documents using LangChain FAISS.
        """
        if not self.text_vectorstore:
            return []
        
        try:
            # Use LangChain similarity search
            if query:
                results = self.text_vectorstore.similarity_search_with_score(
                    query, k=top_k
                )
            elif query_embedding:
                results = self.text_vectorstore.similarity_search_by_vector(
                    query_embedding, k=top_k
                )
            else:
                return []
            
            formatted = []
            for doc, score in results:
                if filter_metadata:
                    if not all(doc.metadata.get(k) == v for k, v in filter_metadata.items()):
                        continue
                
                formatted.append({
                    'id': doc.metadata.get('doc_id', ''),
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'score': float(score),
                    'type': 'text'
                })
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error searching text: {e}")
            return []
    
    def search_images(self, query_embedding: List[float], top_k: int = 5,
                      filter_metadata: Dict = None) -> List[Dict]:
        """Deprecated. Returns empty list."""
        return []

    def delete_by_file_hash(self, file_hash: str) -> int:
        """
        Delete vector entries that belong to a specific document hash.

        Returns:
            Number of removed vector records.
        """
        if not file_hash or not self.text_vectorstore:
            return 0

        try:
            target_hash = str(file_hash)
            index_to_docstore_id = getattr(self.text_vectorstore, 'index_to_docstore_id', {})
            docstore = getattr(self.text_vectorstore, 'docstore', None)
            doc_map = getattr(docstore, '_dict', {}) if docstore else {}

            ids_to_remove = []
            for doc_id in index_to_docstore_id.values():
                doc = doc_map.get(doc_id)
                metadata = getattr(doc, 'metadata', {}) if doc else {}
                doc_hash = str(metadata.get('file_hash', ''))
                if not doc_hash:
                    continue
                if doc_hash == target_hash or doc_hash.startswith(target_hash) or target_hash.startswith(doc_hash):
                    ids_to_remove.append(doc_id)

            if not ids_to_remove:
                return 0

            # Keep order, remove duplicates.
            ids_to_remove = list(dict.fromkeys(ids_to_remove))
            self.text_vectorstore.delete(ids_to_remove)
            self.text_vectorstore.save_local(self.text_index_path)
            logger.info(f"Removed {len(ids_to_remove)} vectors for file hash {target_hash[:12]}")
            return len(ids_to_remove)

        except Exception as e:
            logger.error(f"Error deleting vectors by file hash: {e}")
            return 0
    
    def as_retriever(self, search_kwargs: Dict = None):
        """
        Get LangChain retriever for text search.
        """
        if not self.text_vectorstore:
            return None
        
        return self.text_vectorstore.as_retriever(
            search_kwargs=search_kwargs or {"k": 5}
        )
    
    def get_statistics(self) -> Dict:
        """Get statistics."""
        text_count = 0
        if self.text_vectorstore:
            try:
                text_count = self.text_vectorstore.index.ntotal
            except Exception:
                pass
        
        return {
            'text_documents': text_count,
            'image_documents': 0,
            'backend': 'LangChain FAISS (text only)',
            'persist_directory': self.persist_directory
        }
    
    def reset(self):
        """Reset all indexes."""
        self._text_vectorstore = None
        
        # Delete files
        import shutil
        if os.path.exists(self.text_index_path):
            shutil.rmtree(self.text_index_path, ignore_errors=True)
        
        logger.info("Vector store reset")


# Global instance
multimodal_vector_store = MultimodalVectorStore()
