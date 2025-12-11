"""
RAG Agent using LangChain chains.
Text-only version.
"""
import logging
from typing import List, Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# LangChain
try:
    from langchain.chains import RetrievalQA
    from langchain.chains.combine_documents import create_stuff_documents_chain
    from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnablePassthrough
    LANGCHAIN_CHAINS_AVAILABLE = True
except ImportError:
    RetrievalQA = None
    LANGCHAIN_CHAINS_AVAILABLE = False
    logger.warning("LangChain chains not available")


class MultimodalRAGAgent:
    """
    RAG Agent using LangChain components.
    Named 'MultimodalRAGAgent' for legacy compatibility, but now Text-Only.
    """
    
    def __init__(self):
        """Initialize the RAG agent."""
        self._embedding_service = None
        self._vector_store = None
        self._multimodal_llm = None
        self._retrieval_chain = None
    
    @property
    def embedding_service(self):
        """Lazy load embedding service."""
        if self._embedding_service is None:
            from .embedding_service import embedding_service
            self._embedding_service = embedding_service
        return self._embedding_service
    
    @property
    def vector_store(self):
        """Lazy load vector store."""
        if self._vector_store is None:
            from .multimodal_vector_store import multimodal_vector_store
            self._vector_store = multimodal_vector_store
        return self._vector_store
    
    @property
    def multimodal_llm(self):
        """Lazy load multi-modal LLM (now text focused)."""
        if self._multimodal_llm is None:
            from .multimodal_llm import multimodal_llm
            self._multimodal_llm = multimodal_llm
        return self._multimodal_llm
    
    def get_retrieval_chain(self):
        """
        Get LangChain RetrievalQA chain.
        """
        if self._retrieval_chain is not None:
            return self._retrieval_chain
        
        if not LANGCHAIN_CHAINS_AVAILABLE:
            logger.warning("LangChain chains not available")
            return None
        
        try:
            # Get retriever from vector store
            retriever = self.vector_store.as_retriever(
                search_kwargs={"k": 5}
            )
            
            if retriever is None:
                logger.warning("Retriever not available")
                return None
            
            # Get LLM
            llm = self.multimodal_llm.text_llm
            if llm is None:
                logger.warning("LLM not available")
                return None
            
            # Create prompt template
            prompt = PromptTemplate(
                template="""You are a retrieval-augmented assistant.
Your job is to answer the user using the following pipeline:
1. Always search the vector store first using the user query.
2. Retrieve the most relevant documents.
3. Use ONLY the retrieved chunks as your primary source of truth.
4. If the user asks about content not found in the retrieved documents, clearly say that the information does not exist in the uploaded files.
5. When summarizing or explaining content, stay faithful to the meaning of the original text.
6. If the user uploads new files, extract text and update embeddings immediately.
7. Never hallucinate, never assume facts, and never invent missing details.
8. Respond clearly, concisely, and in a helpful tone.

Context:
{context}

Question: {question}

Answer:""",
                input_variables=["context", "question"]
            )
            
            # Create RetrievalQA chain
            self._retrieval_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=retriever,
                return_source_documents=True,
                chain_type_kwargs={"prompt": prompt}
            )
            
            logger.info("Created LangChain RetrievalQA chain")
            return self._retrieval_chain
            
        except Exception as e:
            logger.error(f"Error creating retrieval chain: {e}")
            return None
    
    def retrieve(self, query: str, top_k: int = 5) -> Dict:
        """
        Retrieve relevant documents using LangChain.
        Text only.
        
        Args:
            query: Text query
            top_k: Number of results
            
        Returns:
            Dict with results and context
        """
        logger.info(f"Retrieving for query: {query[:100]}...")
        
        try:
            # Search text using LangChain vectorstore
            text_results = self.vector_store.search_text(
                query=query, 
                top_k=top_k
            )
            
            # Build context
            context = self._build_context(text_results)
            
            return {
                'text_results': text_results,
                'image_results': [],
                'context': context,
                'query': query
            }
            
        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            return {
                'text_results': [],
                'image_results': [],
                'context': '',
                'query': query,
                'error': str(e)
            }
    
    def _build_context(self, text_results: List[Dict], max_length: int = 4000) -> str:
        """Build context string from results."""
        parts = []
        length = 0
        
        if text_results:
            parts.append(" RELEVANT INFORMATION FROM CAR MANUALS:\n")
            for i, r in enumerate(text_results[:5], 1):
                content = r.get('content', '')
                source = r.get('metadata', {}).get('file_name', 'Unknown')
                page = r.get('metadata', {}).get('page', '?')
                entry = f"\n[{i}] Source: {source} (Page {page})\n{content[:500]}..."
                if length + len(entry) > max_length:
                    break
                parts.append(entry)
                length += len(entry)
        
        return '\n'.join(parts)
    
    def query(self, user_query: str, top_k: int = 5, use_llm: bool = True) -> Dict:
        """
        Complete RAG query using LangChain chain.
        """
        # For text-only queries, try LangChain RetrievalQA first
        if use_llm:
            chain = self.get_retrieval_chain()
            if chain:
                try:
                    result = chain.invoke({"query": user_query})
                    
                    sources = []
                    for doc in result.get('source_documents', []):
                        sources.append({
                            'type': 'text',
                            'file': doc.metadata.get('file_name'),
                            'page': doc.metadata.get('page'),
                            'content': doc.page_content[:200]
                        })
                    
                    return {
                        'success': True,
                        'query': user_query,
                        'answer': result.get('result', ''),
                        'sources': sources,
                        'chain': 'LangChain RetrievalQA'
                    }
                except Exception as e:
                    logger.warning(f"RetrievalQA failed, falling back: {e}")
        
        # Fallback: manual retrieval + LLM
        retrieval_result = self.retrieve(
            user_query, 
            top_k=top_k
        )
        
        if retrieval_result.get('error'):
            return {
                'success': False,
                'query': user_query,
                'error': retrieval_result['error']
            }
        
        # Generate response
        answer = None
        if use_llm:
            answer = self.multimodal_llm.answer_with_context(
                question=user_query,
                text_context=retrieval_result['context']
            )
        
        # Prepare sources
        sources = []
        for r in retrieval_result['text_results']:
            sources.append({
                'type': 'text',
                'file': r.get('metadata', {}).get('file_name'),
                'page': r.get('metadata', {}).get('page'),
                'score': r.get('score')
            })
        
        return {
            'success': True,
            'query': user_query,
            'answer': answer,
            'context': retrieval_result['context'],
            'sources': sources,
            'text_results_count': len(retrieval_result['text_results']),
            'image_results_count': 0,
            'chain': 'Text RAG'
        }
    
    def get_status(self) -> Dict:
        """Get agent status."""
        return {
            'langchain_chains_available': LANGCHAIN_CHAINS_AVAILABLE,
            'retrieval_chain_ready': self._retrieval_chain is not None,
            'embedding_service': self.embedding_service.get_model_info(),
            'vector_store': self.vector_store.get_statistics(),
            'multimodal_llm': self.multimodal_llm.get_status()
        }


# Global instance
multimodal_rag_agent = MultimodalRAGAgent()
