"""
Admin configuration for Complaint model.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    """Admin interface for Complaint model."""
    list_display = [
        'id',
        'car_license_plate',
        'customer_name',
        'category_with_icon',
        'confidence_display',
        'critical_flags',
        'created_at',
    ]
    list_filter = [
        'predicted_category',
        'crash',
        'fire',
        'created_at',
    ]
    search_fields = [
        'complaint_text',
        'car__license_plate',
        'car__customer__name',
    ]
    readonly_fields = [
        'cleaned_text',
        'predicted_category',
        'prediction_confidence',
        'created_at',
        'updated_at',
    ]
    ordering = ['-created_at']
    raw_id_fields = ['car']

    fieldsets = (
        ('Complaint Information', {
            'fields': ('car', 'complaint_text', 'cleaned_text')
        }),
        ('ML Classification', {
            'fields': ('predicted_category', 'prediction_confidence')
        }),
        ('Flags', {
            'fields': ('crash', 'fire')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def car_license_plate(self, obj):
        """Display car license plate."""
        return obj.car.license_plate
    car_license_plate.short_description = 'License Plate'

    def customer_name(self, obj):
        """Display customer name."""
        return obj.customer.name
    customer_name.short_description = 'Customer'

    def category_with_icon(self, obj):
        """Display category with icon."""
        return obj.get_category_display_with_icon()
    category_with_icon.short_description = 'Category'

    def confidence_display(self, obj):
        """Display confidence as percentage with color."""
        confidence = obj.prediction_confidence * 100
        if confidence >= 80:
            color = 'green'
        elif confidence >= 60:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            confidence
        )
    confidence_display.short_description = 'Confidence'

    def critical_flags(self, obj):
        """Display critical flags."""
        flags = []
        if obj.crash:
            flags.append('⚠️ CRASH')
        if obj.fire:
            flags.append('🔥 FIRE')
        return ' '.join(flags) if flags else '-'
    critical_flags.short_description = 'Critical'
