"""
Complaint model for storing customer complaints about their cars.
Each complaint is automatically classified using ML models.
"""
from django.db import models
from apps.cars.models import Car


class ComplaintStatus(models.TextChoices):
    """Status choices for complaint resolution tracking."""
    NEW = 'new', 'New'
    IN_PROGRESS = 'in_progress', 'In Progress'
    RESOLVED = 'resolved', 'Resolved'
    CLOSED = 'closed', 'Closed'


class ComplaintCategory(models.TextChoices):
    """
    Predefined categories for car complaints based on ML model output.
    These categories match the label encoder from the notebook.
    """
    ADVANCED_SAFETY = 'advanced_safety', 'Advanced Safety'
    AIRBAGS_SEATBELTS = 'airbags_seatbelts', 'Airbags & Seatbelts'
    BRAKES_SAFETY = 'brakes_safety', 'Brakes & Safety'
    ELECTRICAL_SYSTEM = 'electrical_system', 'Electrical System'
    ENGINE = 'engine', 'Engine'
    FUEL_SYSTEM = 'fuel_system', 'Fuel System'
    POWER_TRAIN = 'power_train', 'Power Train'
    STEERING_SUSPENSION = 'steering_suspension', 'Steering & Suspension'
    STRUCTURE_BODY = 'structure_body', 'Structure & Body'
    VISIBILITY_LIGHTING = 'visibility_lighting', 'Visibility & Lighting'
    WHEELS_TIRES = 'wheels_tires', 'Wheels & Tires'


class Complaint(models.Model):
    """
    Complaint model to store customer complaints and ML predictions.

    Attributes:
        car: Foreign key to the car this complaint is about
        complaint_text: Original complaint text from customer
        cleaned_text: Pre-processed text for ML model
        predicted_category: ML-predicted category
        prediction_confidence: Confidence score of the prediction (0-1)
        crash: Whether the complaint involves a crash
        fire: Whether the complaint involves a fire
        created_at: Timestamp when complaint was filed
        updated_at: Timestamp when complaint was last updated
    """
    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name='complaints',
        help_text="Car this complaint is about"
    )

    complaint_text = models.TextField(
        help_text="Original complaint text from customer"
    )

    cleaned_text = models.TextField(
        blank=True,
        help_text="Pre-processed text used for ML prediction"
    )

    predicted_category = models.CharField(
        max_length=50,
        choices=ComplaintCategory.choices,
        blank=True,
        null=True,
        help_text="ML-predicted category of the issue"
    )

    prediction_confidence = models.FloatField(
        default=0.0,
        help_text="Confidence score of the ML prediction (0-1)"
    )

    crash = models.BooleanField(
        default=False,
        help_text="Whether this complaint involves a crash"
    )

    fire = models.BooleanField(
        default=False,
        help_text="Whether this complaint involves a fire"
    )

    status = models.CharField(
        max_length=20,
        choices=ComplaintStatus.choices,
        default=ComplaintStatus.NEW,
        help_text="Current status of complaint resolution"
    )

    resolution_notes = models.TextField(
        blank=True,
        default='',
        help_text="Notes about complaint resolution or actions taken"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when complaint was filed"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when complaint was last updated"
    )

    class Meta:
        db_table = 'complaints'
        verbose_name = 'Complaint'
        verbose_name_plural = 'Complaints'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['car', '-created_at']),
            models.Index(fields=['predicted_category']),
            models.Index(fields=['status']),
            models.Index(fields=['crash']),
            models.Index(fields=['fire']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"Complaint for {self.car.license_plate} - {self.predicted_category} ({self.created_at.strftime('%Y-%m-%d')})"

    @property
    def customer(self):
        """Get the customer who filed this complaint."""
        return self.car.customer

    @property
    def is_critical(self):
        """
        Determine if this is a critical complaint (involves crash or fire).
        """
        return self.crash or self.fire

    @property
    def formatted_date(self):
        """Return formatted complaint date."""
        return self.created_at.strftime('%B %d, %Y at %I:%M %p')

    def get_category_display_with_icon(self):
        """
        Get category display name with an appropriate icon.
        """
        icons = {
            'engine': '🔧',
            'electrical_system': '⚡',
            'brakes_safety': '🛑',
            'airbags_seatbelts': '🎯',
            'steering_suspension': '🎡',
            'fuel_system': '⛽',
            'power_train': '⚙️',
            'advanced_safety': '🛡️',
            'structure_body': '🚗',
            'visibility_lighting': '💡',
            'wheels_tires': '🛞',
        }
        icon = icons.get(self.predicted_category, '📝')
        return f"{icon} {self.get_predicted_category_display()}"

    def to_context_string(self):
        """
        Convert complaint to a string format suitable for LLM context.
        Includes all relevant information for diagnosis.
        """
        from django.utils import timezone
        
        flags = []
        if self.crash:
            flags.append("⚠️ CRASH")
        if self.fire:
            flags.append("🔥 FIRE")
        flag_str = " " + " ".join(flags) if flags else ""
        
        # Calculate time elapsed
        time_elapsed = timezone.now() - self.created_at
        if time_elapsed.days > 0:
            time_str = f"{time_elapsed.days} day(s) ago"
        elif time_elapsed.seconds > 3600:
            time_str = f"{time_elapsed.seconds // 3600} hour(s) ago"
        else:
            time_str = f"{time_elapsed.seconds // 60} minute(s) ago"

        result = [
            f"[{self.formatted_date}] ({time_str})",
            f"Category: {self.get_category_display_with_icon()}",
            f"Status: {self.get_status_display()}",
            f"Confidence: {self.prediction_confidence:.1%}",
        ]
        
        if flag_str:
            result.append(f"Flags:{flag_str}")
        
        result.append(f"Description: {self.complaint_text}")
        
        if self.resolution_notes:
            result.append(f"Resolution Notes: {self.resolution_notes}")
        
        return "\n".join(result) + "\n" + "="*50

    def get_similar_complaints(self, limit=5):
        """
        Get similar complaints for the same car in the same category.
        
        Args:
            limit: Maximum number of similar complaints to return
            
        Returns:
            QuerySet: Similar complaints
        """
        return Complaint.objects.filter(
            car=self.car,
            predicted_category=self.predicted_category
        ).exclude(
            id=self.id
        ).order_by('-created_at')[:limit]


class ComplaintDocument(models.Model):
    """
    Document uploaded by user for a specific complaint (e.g., invoices, images).
    These documents are indexed for RAG.
    """
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='documents',
        help_text="Complaint this document belongs to"
    )
    
    file = models.FileField(
        upload_to='complaint_docs/%Y/%m/%d/',
        help_text="Uploaded file"
    )
    
    file_name = models.CharField(
        max_length=255,
        help_text="Original file name"
    )
    
    file_type = models.CharField(
        max_length=20,
        help_text="File type (pdf, image, etc.)"
    )
    
    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )
    
    is_analyzed = models.BooleanField(
        default=False,
        help_text="Whether the document has been processed by RAG"
    )
    
    analysis_error = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if analysis failed"
    )

    class Meta:
        db_table = 'complaint_documents'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.file_name} ({self.complaint})"

