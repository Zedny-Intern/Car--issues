"""
Celery tasks for preparing chat sessions in the background.
"""
import logging

from celery import shared_task

from .bootstrap import prepare_chat_session_sync

logger = logging.getLogger(__name__)


@shared_task(name='chat.prepare_chat_session_for_complaint')
def prepare_chat_session_for_complaint(
    complaint_id: int,
    sync_documents: bool = True,
    source: str = 'background',
):
    logger.info(
        "Preparing chat session for complaint %s (sync_documents=%s, source=%s)",
        complaint_id,
        sync_documents,
        source,
    )
    return prepare_chat_session_sync(
        complaint_id=complaint_id,
        sync_documents=sync_documents,
        source=source,
    )
