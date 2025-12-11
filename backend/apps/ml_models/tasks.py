"""
Celery tasks for async document processing and indexing.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='ml_models.index_static_documents')
def index_static_documents():
    """
    Celery task to index all documents from static and rag_data directories.
    Called on startup or manually via API.
    """
    from .document_loader import document_loader
    
    logger.info("Starting async document indexing...")
    try:
        result = document_loader.index_all_documents()
        logger.info(f"Async indexing complete: {result['processed']} processed, {result['errors']} errors")
        return result
    except Exception as e:
        logger.error(f"Error in async indexing: {e}")
        return {'error': str(e)}


@shared_task(name='ml_models.process_uploaded_document')
def process_uploaded_document(file_path: str, force: bool = False):
    """
    Celery task to process a single uploaded document.
    
    Args:
        file_path: Path to the uploaded file
        force: Force reprocessing even if already indexed
    """
    from .document_loader import document_loader
    
    logger.info(f"Processing uploaded document: {file_path}")
    try:
        result = document_loader.process_file(file_path, force=force)
        logger.info(f"Document processing complete: {result}")
        return result
    except Exception as e:
        logger.error(f"Error processing document {file_path}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ml_models.reindex_all_documents')
def reindex_all_documents():
    """
    Celery task to force reindex all documents.
    Clears existing indexes and reprocesses everything.
    """
    from .document_loader import document_loader
    from .multimodal_vector_store import multimodal_vector_store
    
    logger.info("Starting full reindex...")
    try:
        # Reset vector store
        multimodal_vector_store.reset()
        
        # Reprocess all documents
        result = document_loader.index_all_documents(force=True)
        logger.info(f"Full reindex complete: {result}")
        return result
    except Exception as e:
        logger.error(f"Error during reindex: {e}")
        return {'error': str(e)}


@shared_task(name='ml_models.process_batch_documents')
def process_batch_documents(file_paths: list):
    """
    Celery task to process a batch of documents.
    
    Args:
        file_paths: List of file paths to process
    """
    from .document_loader import document_loader
    
    results = {
        'processed': 0,
        'errors': 0,
        'details': []
    }
    
    for file_path in file_paths:
        try:
            result = document_loader.process_file(file_path)
            if result.get('success'):
                results['processed'] += 1
            else:
                results['errors'] += 1
            results['details'].append(result)
        except Exception as e:
            results['errors'] += 1
            results['details'].append({
                'success': False,
                'file_path': file_path,
                'error': str(e)
            })
    
    return results
