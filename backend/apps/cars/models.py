"""
Car model for storing vehicle information.
Each car belongs to a customer and can have multiple complaints.
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.customers.models import Customer


def validate_car_year(value):
    """
    Validate car year to ensure it's within reasonable range.
    - Not in the future
    - Not too old (>= 1900)
    """
    current_year = timezone.now().year
    if value > current_year + 1:
        raise ValidationError(f"Car year cannot be in the future (max: {current_year + 1}).")
    if value < 1900:
        raise ValidationError("Car year must be 1900 or later.")


class Car(models.Model):
    """
    Car model to store vehicle information.

    Attributes:
        customer: Foreign key to the owner (Customer)
        license_plate: Unique car license plate number
        make: Car manufacturer (e.g., Toyota, BMW)
        model: Car model (e.g., Camry, X5)
        year: Manufacturing year
        vin: Vehicle Identification Number (optional)
        color: Car color (optional)
        mileage: Current mileage in kilometers
        created_at: Timestamp when car was registered
        updated_at: Timestamp when car info was last updated
    """
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='cars',
        help_text="Car owner"
    )

    license_plate = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Unique car license plate number (auto-normalized to uppercase, spaces removed)"
    )

    make = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Car manufacturer (e.g., Toyota, BMW)"
    )

    model = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Car model (e.g., Camry, X5)"
    )

    year = models.IntegerField(
        validators=[validate_car_year],
        null=True,
        blank=True,
        help_text="Manufacturing year (e.g., 2020)"
    )

    vin = models.CharField(
        max_length=17,
        blank=True,
        null=True,
        unique=True,
        help_text="Vehicle Identification Number (17 characters)"
    )

    color = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Car color"
    )

    mileage = models.IntegerField(
        default=0,
        help_text="Current mileage in kilometers"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when car was registered"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when car info was last updated"
    )

    class Meta:
        db_table = 'cars'
        verbose_name = 'Car'
        verbose_name_plural = 'Cars'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['license_plate']),
            models.Index(fields=['vin']),
            models.Index(fields=['customer', '-created_at']),
        ]
        unique_together = [['customer', 'license_plate']]

    def save(self, *args, **kwargs):
        """
        Override save to normalize license plate.
        - Convert to uppercase
        - Remove extra spaces
        """
        if self.license_plate:
            # Normalize: uppercase and remove extra spaces
            self.license_plate = ' '.join(self.license_plate.upper().split())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.make} {self.model} ({self.license_plate})" if self.make else f"Car ({self.license_plate})"

    @property
    def display_name(self):
        """Return a formatted display name for the car."""
        parts = []
        if self.year:
            parts.append(str(self.year))
        if self.make:
            parts.append(self.make)
        if self.model:
            parts.append(self.model)
        return ' '.join(parts) if parts else f"Vehicle {self.license_plate}"

    @property
    def total_complaints(self):
        """Return total number of complaints for this car."""
        return self.complaints.count()

    def get_complaint_history(self):
        """
        Get all complaints for this car, ordered by date (most recent first).
        """
        return self.complaints.order_by('-created_at')

    def get_recent_issues(self, limit=5):
        """
        Get recent issues (complaints) for this car.

        Args:
            limit: Maximum number of recent complaints to return

        Returns:
            QuerySet of recent complaints
        """
        return self.complaints.order_by('-created_at')[:limit]

    def get_complaints_by_category(self):
        """
        Get complaints grouped by category with counts.
        
        Returns:
            dict: Category names as keys, complaint count as values
        """
        from django.db.models import Count
        complaints = self.complaints.values('predicted_category').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {item['predicted_category']: item['count'] for item in complaints}

    def get_recurring_issues(self):
        """
        Detect recurring issues (same category appearing multiple times).
        
        Returns:
            List[dict]: Recurring categories with complaint details
        """
        category_counts = self.get_complaints_by_category()
        recurring = []
        
        for category, count in category_counts.items():
            if count > 1:
                complaints = self.complaints.filter(
                    predicted_category=category
                ).order_by('-created_at')
                
                recurring.append({
                    'category': category,
                    'count': count,
                    'complaints': list(complaints),
                    'first_occurrence': complaints.last().created_at,
                    'last_occurrence': complaints.first().created_at,
                })
        
        return recurring

    def get_full_history_text(self):
        """
        Get a formatted text of the car's complete complaint history
        for use with LLM context.

        Returns:
            str: Formatted history text with recurring issue detection
        """
        complaints = self.get_complaint_history()
        if not complaints.exists():
            return f"No previous complaints for this {self.display_name}."

        history_lines = [
            f"=== Vehicle History: {self.display_name} ===",
            f"License Plate: {self.license_plate}",
            f"Total Complaints: {self.total_complaints}",
        ]

        # Add recurring issues warning
        recurring = self.get_recurring_issues()
        if recurring:
            history_lines.append("\n⚠️ RECURRING ISSUES DETECTED:")
            for issue in recurring:
                history_lines.append(
                    f"  - {issue['category']}: {issue['count']} times "
                    f"(first: {issue['first_occurrence'].strftime('%Y-%m-%d')}, "
                    f"latest: {issue['last_occurrence'].strftime('%Y-%m-%d')})"
                )

        history_lines.append("\nPrevious Issues:")

        for i, complaint in enumerate(complaints[:10], 1):  # Limit to 10 most recent
            history_lines.append(
                f"\n{i}. [{complaint.created_at.strftime('%Y-%m-%d %H:%M')}] "
                f"{complaint.get_predicted_category_display()}"
            )
            if complaint.crash or complaint.fire:
                flags = []
                if complaint.crash:
                    flags.append("⚠️ CRASH")
                if complaint.fire:
                    flags.append("🔥 FIRE")
                history_lines.append(f"   {' '.join(flags)}")
            history_lines.append(f"   {complaint.complaint_text[:200]}...")

        if self.total_complaints > 10:
            history_lines.append(f"\n... and {self.total_complaints - 10} more complaints")

        return "\n".join(history_lines)
