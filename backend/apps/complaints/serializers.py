"""
Serializers for Complaint model.
"""
from rest_framework import serializers
from .models import Complaint, ComplaintCategory, ComplaintDocument
from apps.cars.serializers import CarSerializer, CarListSerializer


class ComplaintDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for uploading and listing complaint documents.
    """
    class Meta:
        model = ComplaintDocument
        fields = [
            'id',
            'complaint',
            'file',
            'file_name',
            'file_type',
            'uploaded_at',
            'is_analyzed',
            'analysis_error',
        ]
        read_only_fields = [
            'id',
            'uploaded_at',
            'file_name',
            'file_type',
            'is_analyzed',
            'analysis_error'
        ]


class ComplaintSerializer(serializers.ModelSerializer):
    """
    Full serializer for Complaint model.
    Includes an `analysis` field that returns the formatted context string
    (used for AI analysis display).
    """
    car = CarSerializer(read_only=True)
    car_id = serializers.PrimaryKeyRelatedField(
        queryset=__import__('apps.cars.models', fromlist=['Car']).Car.objects.all(),
        source='car',
        write_only=True
    )
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    car_display_name = serializers.CharField(source='car.display_name', read_only=True)
    is_critical = serializers.ReadOnlyField()
    formatted_date = serializers.ReadOnlyField()
    category_display = serializers.CharField(source='get_category_display_with_icon', read_only=True)
    # New field – returns the detailed analysis string for this complaint
    analysis = serializers.SerializerMethodField()

    def get_analysis(self, obj):
        """Return the human‑readable analysis string.
        The model provides `to_context_string()` which already formats the
        complaint with date, category, confidence, flags and description.
        """
        try:
            return obj.to_context_string()
        except Exception:
            return ""


    class Meta:
        model = Complaint
        fields = [
            'id',
            'car',
            'car_id',
            'customer_name',
            'car_display_name',
            'complaint_text',
            'cleaned_text',
            'predicted_category',
            'prediction_confidence',
            'category_display',
            'crash',
            'fire',
            'is_critical',
            'formatted_date',
            'created_at',
            'updated_at',
            'analysis',
        ]
        read_only_fields = [
            'id',
            'cleaned_text',
            'predicted_category',
            'prediction_confidence',
            'created_at',
            'updated_at',
        ]


class ComplaintCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new complaints.
    Automatically triggers ML classification.
    """
    car_id = serializers.PrimaryKeyRelatedField(
        queryset=__import__('apps.cars.models', fromlist=['Car']).Car.objects.all(),
        source='car'
    )

    class Meta:
        model = Complaint
        fields = [
            'car_id',
            'complaint_text',
            'crash',
            'fire',
        ]

    def validate_complaint_text(self, value):
        """Validate complaint text."""
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "Complaint text must be at least 10 characters long."
            )
        return value

    def create(self, validated_data):
        """
        Create complaint and run ML classification.
        """
        from apps.ml_models.complaint_classifier import classify_complaint
        from apps.ml_models.text_preprocessing import clean_text

        # Get the complaint text
        complaint_text = validated_data['complaint_text']
        crash = validated_data.get('crash', False)
        fire = validated_data.get('fire', False)

        # Clean the text
        cleaned_text = clean_text(complaint_text)

        # Run ML classification
        prediction = classify_complaint(complaint_text, crash=crash, fire=fire)

        # Create the complaint with predictions
        complaint = Complaint.objects.create(
            car=validated_data['car'],
            complaint_text=complaint_text,
            cleaned_text=cleaned_text,
            predicted_category=prediction.get('category', 'engine'),
            prediction_confidence=prediction.get('confidence', 0.0),
            crash=crash,
            fire=fire
        )

        return complaint


class ComplaintListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing complaints.
    """
    car_license_plate = serializers.CharField(source='car.license_plate', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    category_display = serializers.CharField(source='get_category_display_with_icon', read_only=True)
    is_critical = serializers.ReadOnlyField()
    # New field – formatted analysis string for each complaint
    analysis = serializers.SerializerMethodField()

    def get_analysis(self, obj):
        """Return the same context string used for AI analysis."""
        try:
            return obj.to_context_string()
        except Exception:
            return ""


    class Meta:
        model = Complaint
        fields = [
            'id',
            'car_license_plate',
            'customer_name',
            'predicted_category',
            'category_display',
            'prediction_confidence',
            'crash',
            'fire',
            'is_critical',
            'created_at',
            'complaint_text',
            'analysis',
        ]


class QuickComplaintSubmitSerializer(serializers.Serializer):
    """
    Serializer for quick complaint submission with customer and car info.
    This is used when submitting first-time complaints.
    """
    # Customer info
    customer_name = serializers.CharField(max_length=255)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    customer_phone = serializers.CharField(max_length=17, required=False, allow_blank=True)

    # Car info
    license_plate = serializers.CharField(max_length=20)
    car_make = serializers.CharField(max_length=100, required=False)
    car_model = serializers.CharField(max_length=100, required=False)
    car_year = serializers.IntegerField(required=False)
    car_mileage = serializers.IntegerField(required=False, default=0)

    # Complaint info
    complaint_text = serializers.CharField(min_length=10)
    crash = serializers.BooleanField(default=False)
    fire = serializers.BooleanField(default=False)

    def validate(self, attrs):
        """Validate that at least email or phone is provided."""
        if not attrs.get('customer_email') and not attrs.get('customer_phone'):
            raise serializers.ValidationError(
                "At least one of customer_email or customer_phone must be provided."
            )
        return attrs

    def create(self, validated_data):
        """
        Create customer, car, and complaint in one transaction.
        """
        from django.db import transaction
        from apps.customers.models import Customer
        from apps.cars.models import Car
        from apps.ml_models.complaint_classifier import classify_complaint
        from apps.ml_models.text_preprocessing import clean_text

        with transaction.atomic():
            # 1. Find or create customer
            customer_data = {
                'name': validated_data['customer_name'],
                'email': validated_data.get('customer_email'),
                'phone': validated_data.get('customer_phone'),
            }

            # Try to find existing customer by email or phone
            customer_query = Customer.objects.none()
            if customer_data.get('email'):
                customer_query = Customer.objects.filter(email=customer_data['email'])
            if not customer_query.exists() and customer_data.get('phone'):
                customer_query = Customer.objects.filter(phone=customer_data['phone'])

            if customer_query.exists():
                customer = customer_query.first()
            else:
                customer = Customer.objects.create(**customer_data)

            # 2. Find or create car
            license_plate = validated_data['license_plate']
            try:
                car = Car.objects.get(license_plate__iexact=license_plate)
            except Car.DoesNotExist:
                car = Car.objects.create(
                    customer=customer,
                    license_plate=license_plate.upper(),
                    make=validated_data.get('car_make', 'Unknown'),
                    model=validated_data.get('car_model', 'Unknown'),
                    year=validated_data.get('car_year', 2020),
                    mileage=validated_data.get('car_mileage', 0),
                )

            # 3. Create complaint with ML classification
            complaint_text = validated_data['complaint_text']
            crash = validated_data.get('crash', False)
            fire = validated_data.get('fire', False)

            cleaned_text = clean_text(complaint_text)
            prediction = classify_complaint(complaint_text, crash=crash, fire=fire)

            complaint = Complaint.objects.create(
                car=car,
                complaint_text=complaint_text,
                cleaned_text=cleaned_text,
                predicted_category=prediction.get('category', 'engine'),
                prediction_confidence=prediction.get('confidence', 0.0),
                crash=crash,
                fire=fire
            )

            return {
                'customer': customer,
                'car': car,
                'complaint': complaint
            }
