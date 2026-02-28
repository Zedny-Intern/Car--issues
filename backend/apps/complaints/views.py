"""
Views for Complaint management API.
"""
import logging
from pathlib import Path
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.db.models import Q, Count
from django.conf import settings
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Complaint, ComplaintCategory, ComplaintDocument
from .serializers import (
    ComplaintSerializer,
    ComplaintCreateSerializer,
    ComplaintListSerializer,
    QuickComplaintSubmitSerializer,
    ComplaintDocumentSerializer
)

logger = logging.getLogger(__name__)


class ComplaintViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing complaints.

    Endpoints:
    - GET /api/v1/complaints/ - List all complaints
    - POST /api/v1/complaints/ - Submit new complaint (auto-classifies)
    - GET /api/v1/complaints/{id}/ - Get complaint details
    - PUT/PATCH /api/v1/complaints/{id}/ - Update complaint
    - DELETE /api/v1/complaints/{id}/ - Delete complaint
    - GET /api/v1/complaints/statistics/ - Get complaint statistics
    """
    queryset = Complaint.objects.select_related('car', 'car__customer').all()
    permission_classes = [AllowAny] if settings.DEBUG else [IsAuthenticated]
    public_actions = {'upload_document'}
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['complaint_text', 'car__license_plate', 'car__customer__name']
    ordering_fields = ['created_at', 'prediction_confidence']
    ordering = ['-created_at']

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
            return ComplaintListSerializer
        elif self.action == 'create':
            return ComplaintCreateSerializer
        return ComplaintSerializer

    def get_queryset(self):
        """
        Optionally filter complaints by category, car, customer, or critical flag.
        """
        queryset = super().get_queryset()

        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(predicted_category=category)

        # Filter by car
        car_id = self.request.query_params.get('car_id')
        if car_id:
            queryset = queryset.filter(car_id=car_id)

        # Filter by customer
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(car__customer_id=customer_id)

        # Filter critical complaints only
        critical = self.request.query_params.get('critical')
        if critical and critical.lower() in ['true', '1', 'yes']:
            queryset = queryset.filter(Q(crash=True) | Q(fire=True))

        return queryset

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get complaint statistics.

        Returns counts by category, critical complaints, etc.
        """
        # Total complaints
        total = Complaint.objects.count()

        # By category
        by_category = Complaint.objects.values('predicted_category').annotate(
            count=Count('id')
        ).order_by('-count')

        # Critical complaints
        critical_count = Complaint.objects.filter(
            Q(crash=True) | Q(fire=True)
        ).count()
        crash_count = Complaint.objects.filter(crash=True).count()
        fire_count = Complaint.objects.filter(fire=True).count()

        # Recent complaints (last 7 days)
        from django.utils import timezone
        from datetime import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        recent_count = Complaint.objects.filter(created_at__gte=week_ago).count()

        return Response({
            'total_complaints': total,
            'by_category': by_category,
            'critical_complaints': critical_count,
            'crash_complaints': crash_count,
            'fire_complaints': fire_count,
            'recent_complaints_7days': recent_count,
        })

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """
        Get all available complaint categories.
        """
        categories = [
            {
                'value': choice[0],
                'label': choice[1]
            }
            for choice in ComplaintCategory.choices
        ]
        return Response({'categories': categories})

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_document(self, request, pk=None):
        """
        Upload a document for this complaint and index it for RAG.
        """
        complaint = self.get_object()
        file_obj = request.FILES.get('file')
        from apps.ml_models.document_loader import document_loader
        allowed_extensions = {ext.lstrip('.') for ext in document_loader.SUPPORTED_DOCUMENT_EXTENSIONS}
        allowed_content_types = {
            'pdf': {'application/pdf'},
            'txt': {'text/plain'},
            'md': {'text/markdown', 'text/x-markdown', 'text/plain'},
            'png': {'image/png'},
            'jpg': {'image/jpeg'},
            'jpeg': {'image/jpeg'},
            'webp': {'image/webp'},
            'gif': {'image/gif'},
            'bmp': {'image/bmp'},
        }
        max_size_bytes = 10 * 1024 * 1024
        
        if not file_obj:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        clean_file_name = Path(file_obj.name).name
        extension = Path(clean_file_name).suffix.lower().lstrip('.')
        if extension not in allowed_extensions:
            return Response(
                {'error': f'Unsupported file type: .{extension}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        uploaded_content_type = (file_obj.content_type or '').lower()
        expected_types = allowed_content_types.get(extension, set())
        if uploaded_content_type and expected_types and uploaded_content_type not in expected_types:
            return Response(
                {'error': f'Invalid content type for .{extension}: {uploaded_content_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if file_obj.size > max_size_bytes:
            return Response(
                {'error': f'File exceeds maximum size of {max_size_bytes // (1024 * 1024)}MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            from apps.chat.bootstrap import dispatch_prepare_chat_session

            # 1. Save document to DB
            doc = ComplaintDocument.objects.create(
                complaint=complaint,
                file=file_obj,
                file_name=clean_file_name,
                file_type=extension if extension else 'unknown'
            )
            
            # 2. Process with RAG DocumentLoader
            # Get full path to the saved file
            import os
            from django.conf import settings
            file_path = os.path.join(settings.MEDIA_ROOT, doc.file.name)

            use_async = request.query_params.get('async', 'true').lower() == 'true'
            if use_async:
                from apps.ml_models.tasks import process_uploaded_document
                task = process_uploaded_document.delay(
                    file_path=file_path,
                    force=True,
                    complaint_document_id=doc.id,
                )
                return Response({
                    'success': True,
                    'message': 'Document uploaded. Indexing started in background.',
                    'task_id': task.id,
                    'data': ComplaintDocumentSerializer(doc).data
                }, status=status.HTTP_202_ACCEPTED)

            # Sync fallback (explicit async=false)
            result = document_loader.process_file(file_path, force=True)

            if result.get('success'):
                doc.is_analyzed = True
                doc.save(update_fields=['is_analyzed'])
                dispatch_prepare_chat_session(
                    complaint_id=complaint.id,
                    sync_documents=False,
                    source='complaint-upload-sync',
                )
                return Response({
                    'success': True,
                    'message': 'Document uploaded and indexed successfully',
                    'data': ComplaintDocumentSerializer(doc).data,
                    'rag_result': result
                })

            doc.analysis_error = result.get('error', 'Unknown error')
            doc.save(update_fields=['analysis_error'])
            return Response({
                'success': False,
                'message': 'Document uploaded but indexing failed',
                'error': result.get('error'),
                'data': ComplaintDocumentSerializer(doc).data
            }, status=status.HTTP_202_ACCEPTED)
                
        except Exception:
            logger.exception("Unexpected error while uploading complaint document")
            return Response(
                {'error': 'Unexpected server error while processing the document.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@api_view(['POST'])
@permission_classes(
    [AllowAny]
    if settings.DEBUG or getattr(settings, 'PUBLIC_FRONTEND_API_ENABLED', True)
    else [IsAuthenticated]
)
def quick_submit_complaint(request):
    """
    Quick complaint submission endpoint.

    Handles first-time submissions where customer and car info are provided
    along with the complaint. Creates customer, car, and complaint in one call.

    Required Fields:
    - customer_name: Customer's name
    - customer_email or customer_phone: At least one contact method
    - license_plate: Car's license plate
    - complaint_text: Description of the problem

    Optional Fields:
    - car_make, car_model, car_year, car_mileage: Car details
    - crash: Boolean (default False)
    - fire: Boolean (default False)

    Returns:
    - Created complaint with customer and car info
    - ML classification results
    """
    serializer = QuickComplaintSubmitSerializer(data=request.data)

    if serializer.is_valid():
        try:
            result = serializer.save()
        except DRFValidationError as exc:
            return Response({
                'success': False,
                'errors': exc.detail
            }, status=status.HTTP_400_BAD_REQUEST)

        from apps.customers.serializers import CustomerSerializer
        from apps.cars.serializers import CarSerializer

        return Response({
            'success': True,
            'message': 'Complaint submitted successfully',
            'data': {
                'customer': CustomerSerializer(result['customer']).data,
                'car': CarSerializer(result['car']).data,
                'complaint': ComplaintSerializer(result['complaint']).data,
            }
        }, status=status.HTTP_201_CREATED)

    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)
