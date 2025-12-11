"""
Views for Complaint management API.
"""
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q, Count
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Complaint, ComplaintCategory, ComplaintDocument
from .serializers import (
    ComplaintSerializer,
    ComplaintCreateSerializer,
    ComplaintListSerializer,
    QuickComplaintSubmitSerializer,
    ComplaintDocumentSerializer
)


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
    permission_classes = [AllowAny]  # Change to IsAuthenticated in production
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['complaint_text', 'car__license_plate', 'car__customer__name']
    ordering_fields = ['created_at', 'prediction_confidence']
    ordering = ['-created_at']

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
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_document(self, request, pk=None):
        """
        Upload a document for this complaint and index it for RAG.
        """
        complaint = self.get_object()
        file_obj = request.FILES.get('file')
        
        if not file_obj:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # 1. Save document to DB
            doc = ComplaintDocument.objects.create(
                complaint=complaint,
                file=file_obj,
                file_name=file_obj.name,
                file_type=file_obj.name.split('.')[-1].lower() if '.' in file_obj.name else 'unknown'
            )
            
            # 2. Process with RAG DocumentLoader
            from apps.ml_models.document_loader import document_loader
            
            # Get full path to the saved file
            import os
            from django.conf import settings
            file_path = os.path.join(settings.MEDIA_ROOT, doc.file.name)
            
            # Index it
            result = document_loader.process_file(file_path, force=True)
            
            if result.get('success'):
                doc.is_analyzed = True
                doc.save()
                return Response({
                    'success': True,
                    'message': 'Document uploaded and indexed successfully',
                    'data': ComplaintDocumentSerializer(doc).data,
                    'rag_result': result
                })
            else:
                doc.analysis_error = result.get('error', 'Unknown error')
                doc.save()
                return Response({
                    'success': False,
                    'message': 'Document uploaded but indexing failed',
                    'error': result.get('error'),
                    'data': ComplaintDocumentSerializer(doc).data
                }, status=status.HTTP_202_ACCEPTED) # Accepted but processing failed
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


from django.views.decorators.csrf import csrf_exempt

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
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
        result = serializer.save()

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
