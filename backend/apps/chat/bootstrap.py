"""
Utilities for pre-creating and warming chat sessions in the background.
"""
import logging
import threading

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import ChatMessage, ChatSession, MessageRole

logger = logging.getLogger(__name__)


def _build_placeholder_greeting(session: ChatSession) -> str:
    complaint = session.complaint
    category = complaint.get_predicted_category_display() if complaint.predicted_category else "the issue"
    return (
        f"I've started reviewing your complaint for {complaint.car.display_name}. "
        f"The current predicted category is {category}. "
        "You can start chatting now while I finish preparing the detailed diagnostic context in the background."
    )


def ensure_active_session_for_complaint(complaint, title: str = ""):
    """
    Return the single active session for a complaint, creating it if needed.
    """
    with transaction.atomic():
        sessions = list(
            ChatSession.objects
            .select_for_update()
            .select_related('complaint', 'complaint__car', 'complaint__car__customer')
            .filter(complaint=complaint, is_active=True)
            .order_by('-updated_at', '-id')
        )
        if sessions:
            session = sessions[0]
            duplicate_ids = [item.id for item in sessions[1:]]
            if duplicate_ids:
                ChatSession.objects.filter(id__in=duplicate_ids).update(
                    is_active=False,
                    closed_at=timezone.now(),
                )
            if title and not session.title:
                session.title = title
                session.save(update_fields=['title'])
            return session, False

        try:
            session = ChatSession.objects.create(complaint=complaint, title=title)
            return session, True
        except IntegrityError:
            session = (
                ChatSession.objects
                .select_related('complaint', 'complaint__car', 'complaint__car__customer')
                .filter(complaint=complaint, is_active=True)
                .order_by('-updated_at', '-id')
                .first()
            )
            if session is None:
                raise
            return session, False


def ensure_session_greeting(session: ChatSession, overwrite_placeholder: bool = False):
    """
    Make sure each active session already contains at least one assistant message.
    """
    assistant_message = (
        session.messages
        .filter(role=MessageRole.ASSISTANT)
        .order_by('created_at')
        .first()
    )

    if assistant_message and not overwrite_placeholder:
        return assistant_message, False

    from apps.ml_models.langchain_service import get_mechanic_service

    try:
        greeting = get_mechanic_service().generate_initial_greeting(chat_session=session)
        metadata = {
            **(assistant_message.metadata if assistant_message else {}),
            'bootstrap': 'ai',
        }
    except Exception as exc:
        logger.warning("Falling back to placeholder greeting for session %s: %s", session.id, exc)
        greeting = _build_placeholder_greeting(session)
        metadata = {
            **(assistant_message.metadata if assistant_message else {}),
            'bootstrap': 'placeholder',
        }

    if assistant_message:
        assistant_message.message = greeting
        assistant_message.metadata = metadata
        assistant_message.save(update_fields=['message', 'metadata'])
        return assistant_message, True

    return ChatMessage.objects.create(
        session=session,
        role=MessageRole.ASSISTANT,
        message=greeting,
        metadata=metadata,
    ), True


def ensure_placeholder_greeting(session: ChatSession):
    assistant_message = (
        session.messages
        .filter(role=MessageRole.ASSISTANT)
        .order_by('created_at')
        .first()
    )
    if assistant_message:
        return assistant_message, False

    return ChatMessage.objects.create(
        session=session,
        role=MessageRole.ASSISTANT,
        message=_build_placeholder_greeting(session),
        metadata={'bootstrap': 'placeholder'},
    ), True


def prepare_chat_session_sync(
    complaint_id: int,
    sync_documents: bool = True,
    source: str = 'background',
):
    """
    Fully prepare chat runtime for a complaint:
    - sync/index static + uploaded documents
    - warm RAG + chat runtime
    - create an active chat session + initial AI greeting
    """
    from apps.complaints.models import Complaint
    from apps.ml_models.tasks import prime_rag_runtime_sync

    complaint = (
        Complaint.objects
        .select_related('car', 'car__customer')
        .filter(id=complaint_id)
        .first()
    )
    if complaint is None:
        raise ValueError(f"Complaint {complaint_id} does not exist.")

    runtime_status = prime_rag_runtime_sync(force=False, cleanup_missing=sync_documents)
    session, _ = ensure_active_session_for_complaint(complaint)
    message, greeting_updated = ensure_session_greeting(session, overwrite_placeholder=True)

    metadata = {
        **(session.session_metadata or {}),
        'prepared': True,
        'prepared_source': source,
        'runtime_status': runtime_status,
        'greeting_message_id': message.id,
        'greeting_updated': greeting_updated,
    }
    session.session_metadata = metadata
    session.save(update_fields=['session_metadata'])

    return {
        'session_id': session.id,
        'complaint_id': complaint.id,
        'runtime_status': runtime_status,
        'greeting_updated': greeting_updated,
    }


def dispatch_prepare_chat_session(
    complaint_id: int,
    sync_documents: bool = True,
    source: str = 'background',
):
    """
    Queue chat preparation via Celery when possible, else fall back to a local daemon thread.
    """
    try:
        from .tasks import prepare_chat_session_for_complaint

        task = prepare_chat_session_for_complaint.delay(
            complaint_id=complaint_id,
            sync_documents=sync_documents,
            source=source,
        )
        return {'mode': 'celery', 'task_id': task.id}
    except Exception as exc:
        logger.warning("Falling back to thread-based chat preparation: %s", exc)
        thread = threading.Thread(
            target=prepare_chat_session_sync,
            kwargs={
                'complaint_id': complaint_id,
                'sync_documents': sync_documents,
                'source': source,
            },
            daemon=True,
            name=f'prepare-chat-{complaint_id}',
        )
        thread.start()
        return {'mode': 'thread'}
