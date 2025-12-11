"""
Views for Customer management API.
"""
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q
from .models import Customer
from .serializers import (
    CustomerSerializer,
    CustomerCreateSerializer,
    CustomerListSerializer
)


class CustomerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing customers.

    Endpoints:
    - GET /api/v1/customers/ - List all customers
    - POST /api/v1/customers/ - Create new customer
    - GET /api/v1/customers/{id}/ - Get customer details
    - PUT/PATCH /api/v1/customers/{id}/ - Update customer
    - DELETE /api/v1/customers/{id}/ - Delete customer
    - GET /api/v1/customers/{id}/complaint_history/ - Get all complaints for customer
    """
    queryset = Customer.objects.all()
    permission_classes = [AllowAny]  # Change to IsAuthenticated in production
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'email', 'phone']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return CustomerListSerializer
        elif self.action == 'create':
            return CustomerCreateSerializer
        return CustomerSerializer

    def list(self, request, *args, **kwargs):
        """
        List all customers with optional search.

        Query Parameters:
        - search: Search by name, email, or phone
        - ordering: Order by created_at or name
        """
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Create a new customer.

        Required Fields:
        - name: Customer's full name

        Optional Fields:
        - email: Customer's email
        - phone: Customer's phone number
        - address: Customer's address

        Note: At least one of email or phone must be provided.
        """
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def complaint_history(self, request, pk=None):
        """
        Get complete complaint history for a customer across all their cars.

        Returns all complaints filed by this customer, ordered by date.
        """
        customer = self.get_object()
        complaints = customer.get_complaint_history()

        # Import here to avoid circular import
        from apps.complaints.serializers import ComplaintListSerializer

        serializer = ComplaintListSerializer(complaints, many=True)
        return Response({
            'customer': CustomerSerializer(customer).data,
            'total_complaints': complaints.count(),
            'complaints': serializer.data
        })

    @action(detail=False, methods=['get'])
    def search_by_license_plate(self, request):
        """
        Search for a customer by their car's license plate.

        Query Parameters:
        - plate: License plate number to search
        """
        plate = request.query_params.get('plate', '').strip()
        if not plate:
            return Response(
                {'error': 'Please provide a license plate number'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find car with this plate and return its customer
        from apps.cars.models import Car
        try:
            car = Car.objects.get(license_plate__iexact=plate)
            serializer = CustomerSerializer(car.customer)
            return Response(serializer.data)
        except Car.DoesNotExist:
            return Response(
                {'error': 'No customer found with this license plate'},
                status=status.HTTP_404_NOT_FOUND
            )
