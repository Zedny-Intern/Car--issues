"""
REST API views for document management and multi-modal RAG.
"""
import os
import logging
from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from uuid import uuid4

logger = logging.getLogger(__name__)


def _parse_top_k(raw_value, default=5, min_value=1, max_value=20):
    """
    Parse and clamp top_k-style integer inputs used by retrieval endpoints.
    """
    if raw_value in (None, ''):
        return default

    try:
        parsed = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("top_k must be an integer.") from exc

    if parsed < min_value or parsed > max_value:
        raise ValueError(f"top_k must be between {min_value} and {max_value}.")

    return parsed


class DocumentViewSet(viewsets.ViewSet):
    """
    API endpoints for document management.
    
    Endpoints:
    - POST /api/documents/upload/         Upload a new document
    - GET  /api/documents/                List all indexed documents
    - GET  /api/documents/{id}/           Get document details
    - DELETE /api/documents/{id}/         Delete a document
    - POST /api/documents/reindex/        Trigger full reindex
    - GET  /api/documents/stats/          Get indexing statistics
    """
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny] if settings.DEBUG else [IsAuthenticated]
    public_actions = {'list', 'retrieve', 'upload', 'stats'}

    def get_permissions(self):
        if settings.DEBUG or (
            getattr(settings, 'PUBLIC_FRONTEND_API_ENABLED', True)
            and self.action in self.public_actions
        ):
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]
    
    def list(self, request):
        """List all indexed documents."""
        from apps.ml_models.models import DocumentMetadata
        
        documents = DocumentMetadata.objects.all().order_by('-created_at')
        return Response({
            'count': documents.count(),
            'documents': [
                {
                    'id': doc.id,
                    'file_name': doc.file_name,
                    'file_path': doc.file_path,
                    'file_type': doc.file_type,
                    'file_size': doc.file_size,
                    'indexed': doc.indexed,
                    'indexed_at': doc.indexed_at.isoformat() if doc.indexed_at else None,
                    'page_count': doc.page_count,
                    'created_at': doc.created_at.isoformat()
                }
                for doc in documents[:100]  # Limit to 100
            ]
        })
    
    def retrieve(self, request, pk=None):
        """Get document details including chunks."""
        from apps.ml_models.models import DocumentMetadata
        
        try:
            doc = DocumentMetadata.objects.get(pk=pk)
            chunks = doc.chunks.all()
            
            return Response({
                'id': doc.id,
                'file_name': doc.file_name,
                'file_path': doc.file_path,
                'file_type': doc.file_type,
                'file_size': doc.file_size,
                'indexed': doc.indexed,
                'indexed_at': doc.indexed_at.isoformat() if doc.indexed_at else None,
                'index_error': doc.index_error,
                'page_count': doc.page_count,
                'created_at': doc.created_at.isoformat(),
                'chunks_count': chunks.count(),
                'chunks': [
                    {
                        'chunk_id': c.chunk_id,
                        'type': c.chunk_type,
                        'page': c.page_number,
                        'has_content': bool(c.content),
                        'has_image': bool(c.image_path)
                    }
                    for c in chunks[:50]
                ]
            })
        except DocumentMetadata.DoesNotExist:
            return Response(
                {'error': 'Document not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def destroy(self, request, pk=None):
        """Delete a document and its chunks."""
        from apps.ml_models.models import DocumentMetadata
        from apps.ml_models.multimodal_vector_store import multimodal_vector_store
        
        try:
            doc = DocumentMetadata.objects.get(pk=pk)
            file_hash = doc.file_hash
            
            # Delete from vector store
            multimodal_vector_store.delete_by_file_hash(file_hash)
            
            # Delete from database
            doc.delete()
            
            return Response({'message': f'Document {pk} deleted'})
        except DocumentMetadata.DoesNotExist:
            return Response(
                {'error': 'Document not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def upload(self, request):
        """Upload and process a new document."""
        from apps.ml_models.document_loader import document_loader
        
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES['file']
        safe_name = Path(uploaded_file.name).name
        max_size_bytes = 10 * 1024 * 1024
        if uploaded_file.size > max_size_bytes:
            return Response(
                {'error': f'File exceeds maximum size of {max_size_bytes // (1024 * 1024)}MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file type
        file_ext = Path(safe_name).suffix.lower()
        supported = document_loader.SUPPORTED_DOCUMENT_EXTENSIONS
        content_type = (uploaded_file.content_type or '').lower()
        allowed_content_types = {
            '.pdf': {'application/pdf'},
            '.txt': {'text/plain'},
            '.md': {'text/markdown', 'text/x-markdown', 'text/plain'},
            '.png': {'image/png'},
            '.jpg': {'image/jpeg'},
            '.jpeg': {'image/jpeg'},
            '.webp': {'image/webp'},
            '.gif': {'image/gif'},
            '.bmp': {'image/bmp'},
        }
        
        if file_ext not in supported:
            return Response(
                {'error': f'Unsupported file type: {file_ext}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        expected_types = allowed_content_types.get(file_ext, set())
        if content_type and expected_types and content_type not in expected_types:
            return Response(
                {'error': f'Invalid content type for {file_ext}: {content_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save to uploads directory
        uploads_dir = document_loader.uploads_dir
        os.makedirs(uploads_dir, exist_ok=True)
        unique_name = f"{uuid4().hex}_{safe_name}"
        file_path = os.path.join(uploads_dir, unique_name)
        
        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        
        # Process document (sync or async)
        use_async = request.query_params.get('async', 'false').lower() == 'true'
        
        if use_async:
            from apps.ml_models.tasks import process_uploaded_document
            task = process_uploaded_document.delay(file_path)
            return Response({
                'message': 'Document uploaded, processing started',
                'file_path': file_path,
                'task_id': task.id
            }, status=status.HTTP_202_ACCEPTED)
        else:
            result = document_loader.process_file(file_path)
            if result.get('success'):
                from apps.ml_models.tasks import dispatch_prime_rag_runtime

                dispatch_prime_rag_runtime(force=False, cleanup_missing=False)
                return Response({
                    'message': 'Document uploaded and indexed',
                    'result': result
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'error': 'Processing failed',
                    'result': result
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def reindex(self, request):
        """Trigger full reindex of all documents."""
        use_async = request.query_params.get('async', 'true').lower() == 'true'
        
        if use_async:
            from apps.ml_models.tasks import reindex_all_documents
            task = reindex_all_documents.delay()
            return Response({
                'message': 'Reindex started',
                'task_id': task.id
            }, status=status.HTTP_202_ACCEPTED)
        else:
            from apps.ml_models.document_loader import document_loader
            from apps.ml_models.multimodal_vector_store import multimodal_vector_store
            from apps.ml_models.tasks import dispatch_prime_rag_runtime
            
            multimodal_vector_store.reset()
            result = document_loader.sync_all_documents(force=True, cleanup_missing=True)
            dispatch_prime_rag_runtime(force=False, cleanup_missing=False)
            
            return Response({
                'message': 'Reindex complete',
                'result': result
            })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get indexing statistics."""
        from apps.ml_models.document_loader import document_loader
        
        return Response(document_loader.get_statistics())


class RAGQueryViewSet(viewsets.ViewSet):
    """
    API endpoints for multi-modal RAG queries.
    
    Endpoints:
    - POST /api/rag/query/           Perform a RAG query
    - GET  /api/rag/status/          Get RAG system status
    - POST /api/rag/search/          Search without LLM response
    """
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny] if settings.DEBUG else [IsAuthenticated]
    public_actions = {'query', 'search', 'status'}

    def get_permissions(self):
        if settings.DEBUG or (
            getattr(settings, 'PUBLIC_FRONTEND_API_ENABLED', True)
            and self.action in self.public_actions
        ):
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]
    
    @action(detail=False, methods=['post'])
    def query(self, request):
        """
        Perform a RAG query.
        
        Request body:
        - query: User's question (required)
        - top_k: Number of results (default: 5)
        - use_llm: Whether to generate LLM response (default: true)
        """
        from apps.ml_models.rag_agent import multimodal_rag_agent
        
        query_text = request.data.get('query', '')
        if not query_text:
            return Response(
                {'error': 'Query text is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            top_k = _parse_top_k(request.data.get('top_k', 5), default=5)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        use_llm = request.data.get('use_llm', 'true').lower() == 'true'
        
        # Perform query
        result = multimodal_rag_agent.query(
            user_query=query_text,
            top_k=top_k,
            use_llm=use_llm
        )
        
        return Response(result)
    
    @action(detail=False, methods=['post'])
    def search(self, request):
        """
        Search documents without generating LLM response.
        Returns retrieved documents only.
        """
        from apps.ml_models.rag_agent import multimodal_rag_agent
        
        query_text = request.data.get('query', '')
        if not query_text:
            return Response(
                {'error': 'Query text is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            top_k = _parse_top_k(request.data.get('top_k', 10), default=10)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        
        result = multimodal_rag_agent.retrieve(
            query=query_text,
            top_k=top_k
        )
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get RAG system status."""
        from apps.ml_models.rag_agent import multimodal_rag_agent
        
        return Response(multimodal_rag_agent.get_status())


class ImageViewSet(viewsets.ViewSet):
    """Serve extracted images."""
    permission_classes = [AllowAny] if settings.DEBUG else [IsAuthenticated]

    def get_permissions(self):
        if settings.DEBUG or getattr(settings, 'PUBLIC_FRONTEND_API_ENABLED', True):
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]
    
    @action(detail=False, methods=['get'], url_path='(?P<filename>.+)')
    def serve(self, request, filename=None):
        """Serve an extracted image file."""
        if not filename:
            return Response(
                {'error': 'Image not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        safe_filename = Path(filename).name
        if safe_filename != filename:
            return Response(
                {'error': 'Invalid image path'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        extracted_dir = str(getattr(
            settings, 'RAG_EXTRACTED_IMAGES_DIR',
            Path(settings.BASE_DIR).parent / 'data' / 'extracted_images'
        ))
        
        file_path = os.path.join(extracted_dir, safe_filename)
        
        if not os.path.exists(file_path):
            return Response(
                {'error': 'Image not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return FileResponse(open(file_path, 'rb'))
