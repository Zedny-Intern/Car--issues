"""
Customer model for storing customer information.
Each customer can have multiple cars and complaints.
"""
from django.db import models
from django.core.validators import RegexValidator, MinLengthValidator
from django.core.exceptions import ValidationError


def validate_customer_name(value):
    """
    Validate customer name to ensure it's meaningful.
    - Must be at least 2 characters
    - Should not be all numbers
    """
    if value.strip().isdigit():
        raise ValidationError("Name cannot be only numbers.")
    if len(value.strip()) < 2:
        raise ValidationError("Name must be at least 2 characters long.")


class Customer(models.Model):
    """
    Customer model to store customer personal information.

    Attributes:
        name: Customer's full name (required, minimum 2 characters)
        email: Customer's email address (optional but unique when provided)
        phone: Customer's phone number (optional)
        address: Customer's address (optional)
        created_at: Timestamp when customer was registered
        updated_at: Timestamp when customer information was last updated
    """
    name = models.CharField(
        max_length=255,
        validators=[validate_customer_name],
        help_text="Customer's full name"
    )

    email = models.EmailField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text="Customer's email address (unique)"
    )

    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True,
        help_text="Customer's phone number"
    )

    address = models.TextField(
        blank=True,
        null=True,
        help_text="Customer's address"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when customer was registered"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when customer info was last updated"
    )

    class Meta:
        db_table = 'customers'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['name']),
            models.Index(fields=['created_at']),
        ]

    def clean(self):
        """Validate that customer has at least email or phone."""
        super().clean()
        if not self.email and not self.phone:
            raise ValidationError("Customer must have at least an email or phone number.")

    def save(self, *args, **kwargs):
        """Override save to ensure validation runs."""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.email or self.phone})"

    @property
    def total_cars(self):
        """Return total number of cars owned by this customer."""
        return self.cars.count()

    @property
    def total_complaints(self):
        """Return total number of complaints filed by this customer."""
        return sum(car.complaints.count() for car in self.cars.all())

    @property
    def contact_info(self):
        """Return primary contact information."""
        return self.email or self.phone or "No contact info"

    def get_complaint_history(self):
        """
        Get all complaints for all cars owned by this customer,
        ordered by date (most recent first).
        
        Returns:
            QuerySet: Ordered complaints for all customer's cars
        """
        from apps.complaints.models import Complaint
        return Complaint.objects.filter(
            car__customer=self
        ).select_related('car').order_by('-created_at')

    def get_complaint_timeline(self):
        """
        Get complete complaint timeline with car information.
        
        Returns:
            List[dict]: Timeline entries with complaint and car info
        """
        complaints = self.get_complaint_history()
        timeline = []
        
        for complaint in complaints:
            timeline.append({
                'date': complaint.created_at,
                'formatted_date': complaint.formatted_date,
                'car': complaint.car.display_name,
                'license_plate': complaint.car.license_plate,
                'category': complaint.get_predicted_category_display(),
                'complaint_text': complaint.complaint_text,
                'is_critical': complaint.is_critical,
                'crash': complaint.crash,
                'fire': complaint.fire,
            })
        
        return timeline
