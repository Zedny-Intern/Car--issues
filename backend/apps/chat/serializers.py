"""
Serializers for Chat models.
"""
from rest_framework import serializers
from .models import ChatSession, ChatMessage, MessageRole
from .bootstrap import (
    dispatch_prepare_chat_session,
    ensure_active_session_for_complaint,
    ensure_placeholder_greeting,
)
from apps.complaints.serializers import ComplaintSerializer


class ChatMessageSerializer(serializers.ModelSerializer):
    """
    Serializer for individual chat messages.
    """
    formatted_timestamp = serializers.ReadOnlyField()
    is_from_user = serializers.ReadOnlyField()
    is_from_assistant = serializers.ReadOnlyField()

    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'session',
            'role',
            'message',
            'formatted_timestamp',
            'is_from_user',
            'is_from_assistant',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ChatMessageCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating chat messages (user messages).
    """
    class Meta:
        model = ChatMessage
        fields = ['session', 'message']

    def validate_session(self, value):
        """Ensure session is active."""
        if not value.is_active:
            raise serializers.ValidationError("This chat session is closed.")
        return value

    def create(self, validated_data):
        """
        Create user message only. AI response is now handled by the view for streaming.
        """
        session = validated_data['session']

        # Create user message
        user_message = ChatMessage.objects.create(
            session=session,
            role=MessageRole.USER,
            message=validated_data['message']
        )

        return user_message


class ChatSessionSerializer(serializers.ModelSerializer):
    """
    Full serializer for chat sessions with messages.
    """
    complaint = ComplaintSerializer(read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    car_display = serializers.CharField(source='car.display_name', read_only=True)
    car_license_plate = serializers.CharField(source='car.license_plate', read_only=True)
    total_messages = serializers.ReadOnlyField()
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = [
            'id',
            'complaint',
            'customer_name',
            'car_display',
            'car_license_plate',
            'title',
            'is_active',
            'total_messages',
            'messages',
            'created_at',
            'updated_at',
            'closed_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'closed_at']


class ChatSessionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new chat sessions.
    """
    complaint_id = serializers.PrimaryKeyRelatedField(
        queryset=__import__('apps.complaints.models', fromlist=['Complaint']).Complaint.objects.all(),
        source='complaint'
    )

    class Meta:
        model = ChatSession
        fields = ['id', 'complaint_id', 'title']
        read_only_fields = ['id']

    def create(self, validated_data):
        """
        Create or reuse the active session and return immediately with a placeholder greeting.
        The full runtime and AI greeting are prepared in the background.
        """
        complaint = validated_data['complaint']
        title = validated_data.get('title', '')
        session, _ = ensure_active_session_for_complaint(complaint, title=title)
        ensure_placeholder_greeting(session)
        dispatch_prepare_chat_session(
            complaint_id=complaint.id,
            sync_documents=True,
            source='chat-session-create',
        )

        return session


class ChatSessionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing chat sessions.
    """
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    car_license_plate = serializers.CharField(source='car.license_plate', read_only=True)
    total_messages = serializers.ReadOnlyField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = [
            'id',
            'customer_name',
            'car_license_plate',
            'title',
            'is_active',
            'total_messages',
            'last_message',
            'created_at',
            'updated_at',
        ]

    def get_last_message(self, obj):
        """Get preview of last message."""
        last_msg = obj.messages.last()
        if last_msg:
            preview = last_msg.message[:100]
            if len(last_msg.message) > 100:
                preview += '...'
            return {
                'role': last_msg.role,
                'preview': preview,
                'created_at': last_msg.created_at
            }
        return None
