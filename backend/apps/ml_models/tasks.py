"""
Celery tasks for async document processing and indexing.
"""
import logging
import threading
from celery import shared_task

logger = logging.getLogger(__name__)


def prime_rag_runtime_sync(force: bool = False, cleanup_missing: bool = True):
    """
    Keep the global RAG runtime fresh:
    - sync static/upload/manual documents
    - load embeddings/vector store/chain in background
    """
    from .document_loader import document_loader
    from .rag_agent import multimodal_rag_agent
    from .langchain_service import get_mechanic_service

    sync_result = document_loader.maybe_sync_all_documents(
        force=force,
        cleanup_missing=cleanup_missing,
        min_interval_seconds=0 if force else 30,
    )
    rag_status = multimodal_rag_agent.warm_up()
    chat_status = get_mechanic_service().warm_up(preload_rag=False)
    return {
        'sync_result': sync_result,
        'rag_status': rag_status,
        'chat_status': chat_status,
    }


def dispatch_prime_rag_runtime(force: bool = False, cleanup_missing: bool = True):
    """
    Prefer Celery for background priming, but fall back to a daemon thread if the broker is unavailable.
    """
    try:
        task = prime_rag_runtime.delay(force=force, cleanup_missing=cleanup_missing)
        return {'mode': 'celery', 'task_id': task.id}
    except Exception as exc:
        logger.warning("Falling back to thread-based RAG priming: %s", exc)
        thread = threading.Thread(
            target=prime_rag_runtime_sync,
            kwargs={'force': force, 'cleanup_missing': cleanup_missing},
            daemon=True,
            name='prime-rag-runtime',
        )
        thread.start()
        return {'mode': 'thread'}


@shared_task(name='ml_models.index_static_documents')
def index_static_documents():
    """
    Celery task to index all documents from static and rag_data directories.
    Called on startup or manually via API.
    """
    from .document_loader import document_loader
    
    logger.info("Starting async document indexing...")
    try:
        result = document_loader.sync_all_documents(force=False, cleanup_missing=True)
        logger.info(f"Async indexing complete: {result['processed']} processed, {result['errors']} errors")
        return result
    except Exception as e:
        logger.error(f"Error in async indexing: {e}")
        return {'error': str(e)}


@shared_task(name='ml_models.process_uploaded_document')
def process_uploaded_document(file_path: str, force: bool = False, complaint_document_id: int = None):
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
        if result.get('success'):
            try:
                prime_rag_runtime_sync(force=False, cleanup_missing=False)
            except Exception as warmup_exc:
                logger.warning("RAG warmup after upload failed: %s", warmup_exc)

        if complaint_document_id:
            try:
                from apps.complaints.models import ComplaintDocument
                doc = ComplaintDocument.objects.filter(id=complaint_document_id).first()
                if doc:
                    complaint_id = doc.complaint_id
                    if result.get('success'):
                        doc.is_analyzed = True
                        doc.analysis_error = ''
                    else:
                        doc.analysis_error = result.get('error', 'Unknown indexing error')
                    doc.save(update_fields=['is_analyzed', 'analysis_error'])
                    if result.get('success') and complaint_id:
                        try:
                            from apps.chat.tasks import prepare_chat_session_for_complaint

                            prepare_chat_session_for_complaint.delay(
                                complaint_id=complaint_id,
                                sync_documents=False,
                                source='uploaded-document',
                            )
                        except Exception as prep_exc:
                            logger.warning("Failed to queue chat preparation after upload: %s", prep_exc)
            except Exception as update_exc:
                logger.warning("Failed to update ComplaintDocument %s: %s", complaint_document_id, update_exc)

        logger.info(f"Document processing complete: {result}")
        return result
    except Exception as e:
        if complaint_document_id:
            try:
                from apps.complaints.models import ComplaintDocument
                doc = ComplaintDocument.objects.filter(id=complaint_document_id).first()
                if doc:
                    doc.analysis_error = str(e)
                    doc.save(update_fields=['analysis_error'])
            except Exception:
                pass
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
        result = document_loader.sync_all_documents(force=True, cleanup_missing=True)
        prime_rag_runtime_sync(force=False, cleanup_missing=False)
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


@shared_task(name='ml_models.prime_rag_runtime')
def prime_rag_runtime(force: bool = False, cleanup_missing: bool = True):
    """Background task used on startup and after indexing-related changes."""
    logger.info(
        "Priming RAG runtime (force=%s, cleanup_missing=%s)",
        force,
        cleanup_missing,
    )
    return prime_rag_runtime_sync(force=force, cleanup_missing=cleanup_missing)
