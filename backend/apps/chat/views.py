"""
Views for Chat API.
"""
import os
import tempfile
from pathlib import Path

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import ChatSession, ChatMessage
from .serializers import (
    ChatSessionSerializer,
    ChatSessionCreateSerializer,
    ChatSessionListSerializer,
    ChatMessageSerializer,
    ChatMessageCreateSerializer
)


class ChatSessionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing chat sessions.

    Endpoints:
    - GET /api/v1/chat/ - List all chat sessions
    - POST /api/v1/chat/ - Create new chat session (with initial AI greeting)
    - GET /api/v1/chat/{id}/ - Get session details with all messages
    - PUT/PATCH /api/v1/chat/{id}/ - Update session
    - DELETE /api/v1/chat/{id}/ - Delete session
    - POST /api/v1/chat/{id}/send_message/ - Send a message and get AI response
    - POST /api/v1/chat/{id}/close/ - Close the chat session
    """
    queryset = ChatSession.objects.select_related(
        'complaint',
        'complaint__car',
        'complaint__car__customer'
    ).prefetch_related('messages').all()
    permission_classes = [AllowAny] if settings.DEBUG else [IsAuthenticated]
    public_actions = {'list', 'retrieve', 'create', 'send_message', 'close', 'reopen', 'history'}
    ordering = ['-updated_at']

    def get_permissions(self):
        if settings.DEBUG or (
            getattr(settings, 'PUBLIC_FRONTEND_API_ENABLED', True)
            and self.action in self.public_actions
        ):
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return ChatSessionListSerializer
        elif self.action == 'create':
            return ChatSessionCreateSerializer
        return ChatSessionSerializer

    def get_queryset(self):
        """Filter sessions by complaint, customer, or active status."""
        queryset = super().get_queryset()

        # Filter by complaint
        complaint_id = self.request.query_params.get('complaint_id')
        if complaint_id:
            queryset = queryset.filter(complaint_id=complaint_id)

        # Filter by customer
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(complaint__car__customer_id=customer_id)

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            active_bool = is_active.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_active=active_bool)

        return queryset

    def create(self, request, *args, **kwargs):
        """
        Create a new chat session with initial AI greeting.

        Required:
        - complaint_id: ID of the complaint to discuss

        Optional:
        - title: Custom session title

        Returns: Session with initial AI mechanic greeting
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Always return the full session payload (including initial greeting message).
        instance = ChatSession.objects.select_related(
            'complaint',
            'complaint__car',
            'complaint__car__customer'
        ).prefetch_related('messages').get(id=serializer.instance.id)
        response_data = ChatSessionSerializer(instance).data

        headers = self.get_success_headers(response_data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    @action(
        detail=True,
        methods=['post'],
        parser_classes=[JSONParser, MultiPartParser, FormParser]
    )
    def send_message(self, request, pk=None):
        """
        Send a message in the chat and get AI response.
        Supports optional image uploads.

        Required:
        - message or image(s)
        
        Returns:
        - Streaming AI response (text/plain)
        """
        session = self.get_object()

        if not session.is_active:
            return Response(
                {'error': 'This chat session is closed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract text and optional images.
        message_text = request.data.get('message', '').strip()
        uploaded_images = list(request.FILES.getlist('images'))
        single_image = request.FILES.get('image')
        if single_image:
            uploaded_images.append(single_image)

        # Validate: need text or at least one image.
        if not message_text and not uploaded_images:
            return Response(
                {'error': 'Message text or image is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If only image was sent, create a default prompt.
        if not message_text and uploaded_images:
            message_text = "Please analyze the uploaded image(s) and explain the issue."

        # Validate/prepare temporary image files.
        allowed_types = {
            'image/jpeg',
            'image/jpg',
            'image/png',
            'image/webp',
            'image/gif',
            'image/bmp',
        }
        max_image_size_bytes = 8 * 1024 * 1024
        temp_image_paths = []
        image_names = []

        def cleanup_temp_images():
            for path in temp_image_paths:
                try:
                    os.remove(path)
                except OSError:
                    pass

        for image in uploaded_images:
            content_type = (image.content_type or '').lower()
            if content_type and content_type not in allowed_types:
                cleanup_temp_images()
                return Response(
                    {'error': f'Unsupported image content type: {content_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if image.size > max_image_size_bytes:
                cleanup_temp_images()
                return Response(
                    {'error': f'Image exceeds maximum size of {max_image_size_bytes // (1024 * 1024)}MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            suffix = Path(image.name).suffix or '.img'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                for chunk in image.chunks():
                    tmp_file.write(chunk)
                temp_image_paths.append(tmp_file.name)
                image_names.append(Path(image.name).name)
        
        # Create user message
        message_data = {
            'session': session.id,
            'message': message_text
        }

        serializer = ChatMessageCreateSerializer(data=message_data)
        if serializer.is_valid():
            user_message = serializer.save()
            if image_names:
                user_message.metadata = {
                    'image_names': image_names,
                    'image_count': len(image_names),
                }
                user_message.save(update_fields=['metadata'])

            # Prepare for streaming
            from django.http import StreamingHttpResponse
            from apps.ml_models.langchain_service import get_mechanic_service
            from .models import MessageRole

            def stream_generator():
                full_response = ""
                
                # Regular text-only chat
                service = get_mechanic_service()
                try:
                    # Stream chunks
                    for chunk in service.stream_response(
                        user_message=user_message.message,
                        chat_session=session,
                        use_conversation_memory=True,
                        image_paths=temp_image_paths
                    ):
                        full_response += chunk
                        yield chunk
                finally:
                    cleanup_temp_images()

                # Save the full response to DB after streaming completes
                ChatMessage.objects.create(
                    session=session,
                    role=MessageRole.ASSISTANT,
                    message=full_response
                )

            response = StreamingHttpResponse(
                stream_generator(),
                content_type='text/plain'
            )
            response['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering
            return response

        cleanup_temp_images()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """
        Close the chat session.

        After closing, no more messages can be sent.
        """
        session = self.get_object()

        if not session.is_active:
            return Response(
                {'message': 'Session is already closed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        session.close_session()

        return Response({
            'success': True,
            'message': 'Chat session closed successfully',
            'session': ChatSessionSerializer(session).data
        })

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        """
        Reopen a closed chat session.
        """
        session = self.get_object()

        if session.is_active:
            return Response(
                {'message': 'Session is already active'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            session = ChatSession.objects.select_for_update().get(pk=session.pk)
            ChatSession.objects.select_for_update().filter(
                complaint=session.complaint,
                is_active=True,
            ).exclude(pk=session.pk).update(
                is_active=False,
                closed_at=timezone.now(),
            )
            session.is_active = True
            session.closed_at = None
            session.save()

        return Response({
            'success': True,
            'message': 'Chat session reopened successfully',
            'session': ChatSessionSerializer(session).data
        })

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Get full message history for this session.

        Returns all messages in chronological order.
        """
        session = self.get_object()
        messages = session.messages.order_by('created_at')

        return Response({
            'session_id': session.id,
            'total_messages': messages.count(),
            'messages': ChatMessageSerializer(messages, many=True).data
        })


class ChatMessageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for chat messages.

    Endpoints:
    - GET /api/v1/chat/messages/ - List all messages
    - GET /api/v1/chat/messages/{id}/ - Get message details
    """
    queryset = ChatMessage.objects.select_related('session').all()
    serializer_class = ChatMessageSerializer
    permission_classes = [AllowAny] if settings.DEBUG else [IsAuthenticated]
    ordering = ['created_at']

    def get_queryset(self):
        """Filter messages by session or role."""
        queryset = super().get_queryset()

        # Filter by session
        session_id = self.request.query_params.get('session_id')
        if session_id:
            queryset = queryset.filter(session_id=session_id)

        # Filter by role
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        return queryset
