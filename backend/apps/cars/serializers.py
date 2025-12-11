"""
Serializers for Car model.
"""
from rest_framework import serializers
from .models import Car
from apps.customers.serializers import CustomerSerializer


class CarSerializer(serializers.ModelSerializer):
    """
    Full serializer for Car model.
    """
    customer = CustomerSerializer(read_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=__import__('apps.customers.models', fromlist=['Customer']).Customer.objects.all(),
        source='customer',
        write_only=True
    )
    display_name = serializers.ReadOnlyField()
    total_complaints = serializers.ReadOnlyField()

    class Meta:
        model = Car
        fields = [
            'id',
            'customer',
            'customer_id',
            'license_plate',
            'make',
            'model',
            'year',
            'vin',
            'color',
            'mileage',
            'display_name',
            'total_complaints',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_year(self, value):
        """Validate car year."""
        from django.utils import timezone
        current_year = timezone.now().year
        if value < 1900 or value > current_year + 1:
            raise serializers.ValidationError(
                f"Year must be between 1900 and {current_year + 1}"
            )
        return value

    def validate_license_plate(self, value):
        """Validate license plate format and uniqueness."""
        # Remove spaces and convert to uppercase for consistency
        value = value.replace(' ', '').upper()
        return value


class CarCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new cars.
    """
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=__import__('apps.customers.models', fromlist=['Customer']).Customer.objects.all(),
        source='customer'
    )

    class Meta:
        model = Car
        fields = [
            'customer_id',
            'license_plate',
            'make',
            'model',
            'year',
            'vin',
            'color',
            'mileage',
        ]

    def validate_license_plate(self, value):
        """Validate license plate format and uniqueness."""
        # Remove spaces and convert to uppercase for consistency
        value = value.replace(' ', '').upper()
        return value


class CarListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing cars.
    """
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    display_name = serializers.ReadOnlyField()
    total_complaints = serializers.ReadOnlyField()

    class Meta:
        model = Car
        fields = [
            'id',
            'license_plate',
            'display_name',
            'customer_name',
            'total_complaints',
            'mileage',
            'created_at',
        ]
