"""
Serializers for Customer model.
"""
from rest_framework import serializers
from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for Customer model with computed fields.
    """
    total_cars = serializers.ReadOnlyField()
    total_complaints = serializers.ReadOnlyField()

    class Meta:
        model = Customer
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'address',
            'total_cars',
            'total_complaints',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_phone(self, value):
        """Validate phone number format."""
        if value and not value.replace('+', '').replace(' ', '').isdigit():
            raise serializers.ValidationError("Phone number must contain only digits and optional '+'")
        return value


class CustomerCreateSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for creating new customers.
    """
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone', 'address']

    def validate(self, attrs):
        """Ensure at least email or phone is provided."""
        if not attrs.get('email') and not attrs.get('phone'):
            raise serializers.ValidationError(
                "At least one of email or phone must be provided."
            )
        return attrs


class CustomerListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing customers.
    """
    total_cars = serializers.ReadOnlyField()

    class Meta:
        model = Customer
        fields = ['id', 'name', 'email', 'phone', 'total_cars', 'created_at']
