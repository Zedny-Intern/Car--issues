"""
DocumentLoader using pure LangChain components.
Text processing only.
"""
import os
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from django.conf import settings

logger = logging.getLogger(__name__)

# LangChain Components
try:
    from langchain_community.document_loaders import PyMuPDFLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
    LANGCHAIN_AVAILABLE = True
except ImportError:
    PyMuPDFLoader = None
    RecursiveCharacterTextSplitter = None
    Document = None
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain loaders not available")


class DocumentLoader:
    """
    Document Loader using pure LangChain components.
    
    - PyMuPDFLoader: PDF text extraction
    - RecursiveCharacterTextSplitter: Text chunking
    - LangChain FAISS: Vector storage
    """
    
    SUPPORTED_PDF_EXTENSIONS = {'.pdf', '.txt', '.doc', '.docx', '.md'}
    
    def __init__(self):
        """Initialize with paths from settings."""
        self.static_dir = str(getattr(
            settings, 'RAG_DATA_STATIC_DIR',
            Path(settings.BASE_DIR).parent / 'data' / 'static'
        ))
        self.uploads_dir = str(getattr(
            settings, 'RAG_DATA_UPLOADS_DIR',
            Path(settings.BASE_DIR).parent / 'data' / 'uploads'
        ))
        self.rag_data_dir = str(getattr(
            settings, 'RAG_DATA_DIR',
            Path(settings.BASE_DIR).parent / 'rag data'
        ))
        
        # Ensure directories exist
        for d in [self.static_dir, self.uploads_dir]:
            os.makedirs(d, exist_ok=True)
        
        # LangChain text splitter
        self.text_splitter = None
        if LANGCHAIN_AVAILABLE:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
        
        # Lazy loaded services
        self._embedding_service = None
        self._vector_store = None
    
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
    
    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA-256 hash."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except FileNotFoundError:
            return ""
    
    def get_file_type(self, file_path: str) -> Optional[str]:
        """Get file type from extension."""
        ext = Path(file_path).suffix.lower()
        if ext in self.SUPPORTED_PDF_EXTENSIONS:
            return 'pdf'
        return None
    
    def scan_all_directories(self) -> Dict[str, List[str]]:
        """Scan all directories for files."""
        result = {'static': [], 'uploads': [], 'rag_data': []}
        
        for key, directory in [
            ('static', self.static_dir),
            ('uploads', self.uploads_dir),
            ('rag_data', self.rag_data_dir)
        ]:
            if os.path.exists(directory):
                for root, _, files in os.walk(directory):
                    for f in files:
                        path = os.path.join(root, f)
                        if self.get_file_type(path):
                            result[key].append(path)
        
        return result
    
    def is_already_indexed(self, file_path: str) -> bool:
        """Check if file already indexed."""
        try:
            from .models import DocumentMetadata
            file_hash = self.compute_file_hash(file_path)
            return DocumentMetadata.objects.filter(
                file_hash=file_hash, indexed=True
            ).exists()
        except Exception:
            return False
    
    def process_pdf(self, file_path: str) -> Dict:
        """
        Process PDF (or text) using LangChain.
        """
        from .models import DocumentMetadata, DocumentChunk
        
        logger.info(f"Processing document with LangChain: {file_path}")
        
        if not LANGCHAIN_AVAILABLE:
            return {'success': False, 'error': 'LangChain not available'}
        
        try:
            file_hash = self.compute_file_hash(file_path)
            file_name = os.path.basename(file_path)
            
            # 1. Load with LangChain
            # For simplicity using PyMuPDFLoader for everything that fits, or TextLoader
            if file_path.endswith('.txt') or file_path.endswith('.md'):
                from langchain_community.document_loaders import TextLoader
                loader = TextLoader(file_path, encoding='utf-8')
            else:
                loader = PyMuPDFLoader(file_path)
                
            documents = loader.load()
            
            # Create/update metadata
            doc_metadata, _ = DocumentMetadata.objects.update_or_create(
                file_path=file_path,
                defaults={
                    'file_name': file_name,
                    'file_hash': file_hash,
                    'file_type': 'pdf', # Generalizing text docs as 'pdf' type in DB for now or 'text'
                    'file_size': os.path.getsize(file_path),
                    'page_count': len(documents),
                    'indexed': False
                }
            )
            
            # 2. Split with LangChain RecursiveCharacterTextSplitter
            chunks = self.text_splitter.split_documents(documents)
            
            # 3. Process text chunks
            text_docs = []
            for i, chunk in enumerate(chunks):
                content = chunk.page_content
                if not content.strip():
                    continue
                
                chunk_id = f"txt_{file_hash[:8]}_{i}"
                page_num = chunk.metadata.get('page', 0) + 1
                
                text_docs.append({
                    'id': chunk_id,
                    'content': content,
                    'metadata': {
                        'file_hash': file_hash,
                        'file_name': file_name,
                        'page': page_num,
                        'chunk_id': chunk_id,
                        'source': file_path
                    }
                })
                
                # Save to DB
                DocumentChunk.objects.update_or_create(
                    chunk_id=chunk_id,
                    defaults={
                        'document': doc_metadata,
                        'chunk_type': 'text',
                        'page_number': page_num,
                        'content': content[:5000],
                        'text_vector_id': chunk_id
                    }
                )
            
            # 4. Add to LangChain FAISS vectorstore
            if text_docs:
                self.vector_store.add_text_documents(text_docs)
            
            # Mark indexed
            doc_metadata.mark_indexed()
            
            return {
                'success': True,
                'file_path': file_path,
                'text_chunks': len(text_docs),
                'image_chunks': 0,
                'pages': len(documents),
                'loader': 'LangChain Loader'
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            try:
                doc = DocumentMetadata.objects.get(file_path=file_path)
                doc.mark_error(str(e))
            except:
                pass
            return {'success': False, 'error': str(e)}
    
    def process_file(self, file_path: str, force: bool = False) -> Dict:
        """Process a file based on type."""
        if not force and self.is_already_indexed(file_path):
            return {'success': True, 'skipped': True}
        
        # Treat all supported files as 'pdf' (text document) process flow
        file_type = self.get_file_type(file_path)
        
        if file_type == 'pdf':
            return self.process_pdf(file_path)
        
        return {'success': False, 'error': 'Unsupported file type'}
    
    def index_all_documents(self, force: bool = False) -> Dict:
        """Index all documents from all directories."""
        all_files = self.scan_all_directories()
        results = {
            'total': 0,
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'loader': 'LangChain' if LANGCHAIN_AVAILABLE else 'N/A'
        }
        
        for files in all_files.values():
            for path in files:
                results['total'] += 1
                try:
                    result = self.process_file(path, force=force)
                    if result.get('skipped'):
                        results['skipped'] += 1
                    elif result.get('success'):
                        results['processed'] += 1
                    else:
                        results['errors'] += 1
                except Exception as e:
                    results['errors'] += 1
                    logger.error(f"Error: {e}")
        
        return results
    
    def get_statistics(self) -> Dict:
        """Get statistics."""
        from .models import DocumentMetadata, DocumentChunk
        
        all_files = self.scan_all_directories()
        
        return {
            'directories': {
                'static': self.static_dir,
                'uploads': self.uploads_dir,
                'rag_data': self.rag_data_dir
            },
            'files_on_disk': sum(len(f) for f in all_files.values()),
            'documents_in_db': DocumentMetadata.objects.count(),
            'indexed_documents': DocumentMetadata.objects.filter(indexed=True).count(),
            'total_chunks': DocumentChunk.objects.count(),
            'langchain_available': LANGCHAIN_AVAILABLE,
            'vector_store': self.vector_store.get_statistics()
        }


# Global instance
document_loader = DocumentLoader()


def startup_index_documents():
    """Startup indexing."""
    logger.info("Starting document indexing...")
    result = document_loader.index_all_documents()
    logger.info(f"Indexing complete: {result}")
