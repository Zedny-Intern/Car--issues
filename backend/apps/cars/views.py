"""
Views for Car management API.
"""
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Car
from .serializers import (
    CarSerializer,
    CarCreateSerializer,
    CarListSerializer
)


class CarViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing cars.

    Endpoints:
    - GET /api/v1/cars/ - List all cars
    - POST /api/v1/cars/ - Register new car
    - GET /api/v1/cars/{id}/ - Get car details
    - PUT/PATCH /api/v1/cars/{id}/ - Update car
    - DELETE /api/v1/cars/{id}/ - Delete car
    - GET /api/v1/cars/{id}/complaint_history/ - Get complaint history
    - GET /api/v1/cars/{id}/full_history_text/ - Get formatted history for LLM
    """
    queryset = Car.objects.select_related('customer').all()
    permission_classes = [AllowAny]  # Change to IsAuthenticated in production
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['license_plate', 'make', 'model', 'vin', 'customer__name']
    ordering_fields = ['created_at', 'make', 'year']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return CarListSerializer
        elif self.action == 'create':
            return CarCreateSerializer
        return CarSerializer

    @action(detail=True, methods=['get'])
    def complaint_history(self, request, pk=None):
        """
        Get complete complaint history for this car.

        Returns all complaints filed for this car, ordered by date.
        """
        car = self.get_object()
        complaints = car.get_complaint_history()

        # Import here to avoid circular import
        from apps.complaints.serializers import ComplaintListSerializer

        serializer = ComplaintListSerializer(complaints, many=True)
        return Response({
            'car': CarSerializer(car).data,
            'total_complaints': complaints.count(),
            'complaints': serializer.data
        })

    @action(detail=True, methods=['get'])
    def full_history_text(self, request, pk=None):
        """
        Get formatted complaint history text for LLM context.

        Returns a formatted text representation of the car's complete
        complaint history, suitable for feeding to LLM models.
        """
        car = self.get_object()
        history_text = car.get_full_history_text()

        return Response({
            'car_id': car.id,
            'license_plate': car.license_plate,
            'history_text': history_text
        })

    @action(detail=False, methods=['get'])
    def by_license_plate(self, request):
        """
        Get car details by license plate.

        Query Parameters:
        - plate: License plate number to search (required)

        Returns car details if found.
        """
        plate = request.query_params.get('plate', '').strip()
        if not plate:
            return Response(
                {'error': 'Please provide a license plate number'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Normalize plate (remove spaces)
        normalized_plate = plate.replace(' ', '')

        # Strategy 1: Try normalized search (preferred for new data)
        car = Car.objects.select_related('customer').filter(
            license_plate__iexact=normalized_plate
        ).first()

        # Strategy 2: If not found, try original input (for legacy data with spaces)
        if not car and plate != normalized_plate:
            car = Car.objects.select_related('customer').filter(
                license_plate__iexact=plate
            ).first()

        if car:
            serializer = CarSerializer(car)
            return Response(serializer.data)
        else:
            return Response(
                {'error': f'No car found with license plate: {plate}'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['post'])
    def find_or_create(self, request):
        """
        Find an existing car by license plate or create a new one.

        This is useful for the complaint submission flow where we first
        check if the car exists before creating it.

        Required Fields:
        - license_plate: Car's license plate
        - customer_id: Customer ID

        Optional Fields (only used if creating):
        - make, model, year, vin, color, mileage

        Returns:
        - existing car if found
        - newly created car if not found
        """
        license_plate = request.data.get('license_plate', '').strip()
        if not license_plate:
            return Response(
                {'error': 'license_plate is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Try to find existing car
        try:
            car = Car.objects.select_related('customer').get(
                license_plate__iexact=license_plate
            )
            serializer = CarSerializer(car)
            return Response({
                'car': serializer.data,
                'created': False
            })
        except Car.DoesNotExist:
            # Create new car
            serializer = CarCreateSerializer(data=request.data)
            if serializer.is_valid():
                car = serializer.save()
                return Response({
                    'car': CarSerializer(car).data,
                    'created': True
                }, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
