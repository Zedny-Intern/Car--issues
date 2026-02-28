"""
Chat models for storing conversation sessions and messages.
Each chat session is linked to a specific complaint and maintains history.
"""
import re

from django.db import models
from django.db.models import Q
from apps.complaints.models import Complaint


class ChatSession(models.Model):
    """
    Chat session model to group related messages for a specific complaint.

    Attributes:
        complaint: The complaint this chat session is about
        title: Session title (auto-generated or custom)
        is_active: Whether this session is currently active
        created_at: When the session was started
        updated_at: When the session was last updated
        closed_at: When the session was closed (if applicable)
    """
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
        help_text="The complaint this chat is about"
    )

    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Chat session title"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this chat session is active"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the chat session started"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the chat session was last updated"
    )

    closed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the chat session was closed"
    )

    session_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Session metadata (model used, tokens consumed, etc.)"
    )

    class Meta:
        db_table = 'chat_sessions'
        verbose_name = 'Chat Session'
        verbose_name_plural = 'Chat Sessions'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['complaint', '-created_at']),
            models.Index(fields=['is_active']),
            models.Index(fields=['-updated_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['complaint'],
                condition=Q(is_active=True),
                name='unique_active_chat_session_per_complaint',
            ),
        ]

    def __str__(self):
        return f"Chat Session: {self.title or f'#{self.id}'} - {self.complaint.car.license_plate}"

    def save(self, *args, **kwargs):
        """Auto-generate title if not provided."""
        if not self.title and self.complaint:
            category_display = self.complaint.get_predicted_category_display() if self.complaint.predicted_category else "issue"
            self.title = f"Chat about {category_display}"
        super().save(*args, **kwargs)

    @property
    def total_messages(self):
        """Return total number of messages in this session."""
        return self.messages.count()

    @property
    def customer(self):
        """Get the customer for this chat session."""
        return self.complaint.car.customer

    @property
    def car(self):
        """Get the car for this chat session."""
        return self.complaint.car

    @staticmethod
    def _normalize_context_text(value, max_length=280):
        normalized = " ".join((value or "").replace("\x00", " ").split())
        if max_length and len(normalized) > max_length:
            return normalized[:max_length].rstrip() + "..."
        return normalized

    @staticmethod
    def _tokenize_query(value):
        return {
            token
            for token in re.split(r'[^0-9A-Za-z\u0600-\u06FF]+', (value or '').lower())
            if len(token) > 1
        }

    @staticmethod
    def _normalize_reference_text(value):
        return re.sub(r'[^0-9A-Za-z\u0600-\u06FF]+', ' ', (value or '').lower()).strip()

    def get_uploaded_document_paths(self):
        paths = []
        for doc in self.complaint.documents.order_by('-uploaded_at'):
            try:
                path = str(doc.file.path)
            except Exception:
                path = ''
            if path:
                paths.append(path)
        return paths

    def resolve_uploaded_document_reference(self, reference_query=None):
        uploaded_documents = list(self.complaint.documents.order_by('-uploaded_at')[:5])
        if not uploaded_documents:
            return None

        normalized_query = self._normalize_reference_text(reference_query)
        if not normalized_query:
            return None

        query_tokens = self._tokenize_query(normalized_query)
        generic_document_terms = {
            'file', 'files', 'document', 'documents', 'doc', 'docs', 'attachment',
            'attachments', 'upload', 'uploaded', 'attach', 'attached', 'pdf', 'bdf',
            'pfd', 'report', 'reports', 'paper', 'papers', 'scan', 'scans',
            'ملف', 'الملف', 'ملفات', 'فايل', 'فایل', 'مستند', 'المستند',
            'وثيقة', 'الوثيقة', 'مرفق', 'المرفق', 'مرفقات', 'المرفقات',
            'مرفوع', 'المرفوع', 'مرفوعه', 'المرفوعة', 'مرفوعين',
            'تقرير', 'التقرير', 'تقارير', 'pdf', 'بي', 'دي', 'اف',
        }
        content_request_terms = {
            'content', 'contents', 'inside', 'summary', 'summarize', 'explain',
            'show', 'read', 'review', 'what', 'tell',
            'محتوى', 'محتوي', 'ملخص', 'الخلاصة', 'الخلاصه', 'جوه', 'داخل',
            'فيه', 'فيها', 'الموجود', 'اقرا', 'اقرأ', 'راجع', 'وريني',
            'ايه', 'إيه', 'شنو', 'شنوهو',
        }

        best_document = None
        best_score = 0

        for document in uploaded_documents:
            file_name_tokens = self._tokenize_query(document.file_name)
            overlap_score = len(query_tokens & file_name_tokens)
            if overlap_score > best_score:
                best_score = overlap_score
                best_document = document

        references_document_generically = bool(query_tokens & generic_document_terms)
        asks_for_contents = bool(query_tokens & content_request_terms)

        if best_document and best_score > 0:
            match_reason = 'filename-match'
            selected_document = best_document
        elif references_document_generically or (len(uploaded_documents) == 1 and asks_for_contents):
            match_reason = 'latest-upload'
            selected_document = uploaded_documents[0]
        else:
            return None

        try:
            file_path = str(selected_document.file.path)
        except Exception:
            file_path = ''

        return {
            'id': selected_document.id,
            'file_name': selected_document.file_name,
            'file_type': selected_document.file_type,
            'uploaded_at': selected_document.uploaded_at,
            'is_analyzed': selected_document.is_analyzed,
            'analysis_error': selected_document.analysis_error or '',
            'file_path': file_path,
            'match_reason': match_reason,
        }

    def get_uploaded_documents_context(
        self,
        max_documents=3,
        max_excerpts_per_document=2,
        reference_query=None,
    ):
        uploaded_documents = list(
            self.complaint.documents.order_by('-uploaded_at')[:max_documents]
        )
        if not uploaded_documents:
            return []

        from apps.ml_models.models import DocumentMetadata

        document_paths = {}
        for document in uploaded_documents:
            try:
                document_paths[document.id] = str(document.file.path)
            except Exception:
                document_paths[document.id] = ''

        indexed_metadata = {
            metadata.file_path: metadata
            for metadata in (
                DocumentMetadata.objects
                .filter(file_path__in=[path for path in document_paths.values() if path])
                .prefetch_related('chunks')
            )
        }

        query_tokens = self._tokenize_query(reference_query)
        documents_context = []

        for uploaded_document in uploaded_documents:
            file_path = document_paths.get(uploaded_document.id, '')
            metadata = indexed_metadata.get(file_path)
            chunk_list = list(metadata.chunks.all()) if metadata else []

            ranked_chunks = []
            for chunk in chunk_list:
                raw_text = chunk.content or chunk.caption or ''
                cleaned_text = self._normalize_context_text(raw_text, max_length=320)
                if not cleaned_text:
                    continue

                if query_tokens:
                    score = len(query_tokens & self._tokenize_query(raw_text))
                else:
                    score = 0
                if chunk.chunk_type == 'text':
                    score += 0.1

                ranked_chunks.append({
                    'score': score,
                    'page': chunk.page_number,
                    'chunk_type': chunk.chunk_type,
                    'text': cleaned_text,
                })

            if query_tokens:
                ranked_chunks.sort(key=lambda item: (-item['score'], item['page'], item['chunk_type']))
            else:
                ranked_chunks.sort(key=lambda item: (item['page'], 0 if item['chunk_type'] == 'text' else 1))

            documents_context.append({
                'id': uploaded_document.id,
                'file_name': uploaded_document.file_name,
                'file_type': uploaded_document.file_type,
                'uploaded_at': uploaded_document.uploaded_at,
                'is_latest_upload': uploaded_document == uploaded_documents[0],
                'is_analyzed': uploaded_document.is_analyzed,
                'analysis_error': uploaded_document.analysis_error or '',
                'is_indexed': bool(metadata and metadata.indexed),
                'index_error': metadata.index_error if metadata else '',
                'page_count': metadata.page_count if metadata else None,
                'chunk_count': len(chunk_list),
                'excerpts': ranked_chunks[:max_excerpts_per_document],
            })

        return documents_context

    def get_messages_for_context(self, limit=None):
        """
        Get formatted messages for LLM context.

        Args:
            limit: Maximum number of recent messages to include (None = all)

        Returns:
            List of message dictionaries with role and content
        """
        messages_query = self.messages.order_by('created_at')
        if limit:
            # Keep chronological order but restrict to the most recent messages.
            recent_ids = list(
                self.messages.order_by('-created_at').values_list('id', flat=True)[:limit]
            )
            messages_query = self.messages.filter(id__in=recent_ids).order_by('created_at')

        return [
            {
                'role': msg.role,
                'content': msg.message
            }
            for msg in messages_query
        ]

    def close_session(self):
        """Mark this chat session as closed."""
        from django.utils import timezone
        self.is_active = False
        self.closed_at = timezone.now()
        self.save()

    def get_conversation_summary(self):
        """
        Get a summary of the conversation.
        
        Returns:
            dict: Summary with message counts and key info
        """
        messages = self.messages.all()
        user_messages = messages.filter(role=MessageRole.USER)
        assistant_messages = messages.filter(role=MessageRole.ASSISTANT)
        
        return {
            'total_messages': messages.count(),
            'user_messages': user_messages.count(),
            'assistant_messages': assistant_messages.count(),
            'started_at': self.created_at,
            'last_updated': self.updated_at,
            'is_active': self.is_active,
            'duration_minutes': (self.updated_at - self.created_at).total_seconds() / 60,
        }

    def build_full_context_for_llm(self, include_message_limit=10, reference_query=None):
        """
        Build complete context for LLM including:
        - Vehicle information
        - Current complaint (marked as CURRENT/NEW)
        - Historical complaints  
        - Conversation history
        
        Args:
            include_message_limit: Max number of recent messages to include
            
        Returns:
            dict: Complete context with all information
        """
        car = self.complaint.car
        
        # Get conversation history
        conversation_messages = self.get_messages_for_context(limit=include_message_limit)
        
        # Get car's historical complaints (excluding current one)
        historical_complaints = car.get_complaint_history().exclude(
            id=self.complaint.id
        )[:5]
        
        uploaded_documents = self.get_uploaded_documents_context(
            reference_query=reference_query
        )

        context = {
            'vehicle': {
                'display_name': car.display_name,
                'license_plate': car.license_plate,
                'make': car.make,
                'model': car.model,
                'year': car.year,
                'mileage': car.mileage,
                'total_complaints': car.total_complaints,
            },
            'current_complaint': {
                'id': self.complaint.id,
                'text': self.complaint.complaint_text,
                'category': self.complaint.get_predicted_category_display(),
                'confidence': self.complaint.prediction_confidence,
                'crash': self.complaint.crash,
                'fire': self.complaint.fire,
                'status': self.complaint.get_status_display(),
                'created_at': self.complaint.formatted_date,
                'is_critical': self.complaint.is_critical,
            },
            'historical_complaints': [
                {
                    'date': c.formatted_date,
                    'category': c.get_predicted_category_display(),
                    'text': c.complaint_text[:200],
                    'crash': c.crash,
                    'fire': c.fire,
                }
                for c in historical_complaints
            ],
            'conversation_history': conversation_messages,
            'recurring_issues': car.get_recurring_issues(),
            'uploaded_documents': uploaded_documents,
            'uploaded_documents_count': len(uploaded_documents),
        }
        
        return context


class MessageRole(models.TextChoices):
    """Message role types for chat."""
    USER = 'user', 'User'
    ASSISTANT = 'assistant', 'Assistant (AI Mechanic)'
    SYSTEM = 'system', 'System'


class ChatMessage(models.Model):
    """
    Individual chat message within a session.

    Attributes:
        session: The chat session this message belongs to
        role: Who sent the message (user, assistant, or system)
        message: The message content
        created_at: When the message was sent
        metadata: Additional metadata (JSON format)
    """
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="The chat session this message belongs to"
    )

    role = models.CharField(
        max_length=20,
        choices=MessageRole.choices,
        help_text="Message sender role"
    )

    message = models.TextField(
        help_text="Message content"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the message was sent"
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional message metadata"
    )

    class Meta:
        db_table = 'chat_messages'
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        preview = self.message[:50] + '...' if len(self.message) > 50 else self.message
        return f"[{self.role}] {preview}"

    @property
    def is_from_user(self):
        """Check if message is from user."""
        return self.role == MessageRole.USER

    @property
    def is_from_assistant(self):
        """Check if message is from AI assistant."""
        return self.role == MessageRole.ASSISTANT

    @property
    def formatted_timestamp(self):
        """Return formatted timestamp."""
        return self.created_at.strftime('%B %d, %Y at %I:%M %p')
