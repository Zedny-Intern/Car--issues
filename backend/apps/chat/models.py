"""
Chat models for storing conversation sessions and messages.
Each chat session is linked to a specific complaint and maintains history.
"""
from django.db import models
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
            messages_query = messages_query[:limit]

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

    def build_full_context_for_llm(self, include_message_limit=10):
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
