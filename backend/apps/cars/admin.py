"""
Admin configuration for Car model.
"""
from django.contrib import admin
from .models import Car


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    """Admin interface for Car model."""
    list_display = [
        'license_plate',
        'display_name',
        'customer',
        'mileage',
        'total_complaints',
        'created_at'
    ]
    list_filter = ['make', 'year', 'created_at']
    search_fields = ['license_plate', 'vin', 'make', 'model', 'customer__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    raw_id_fields = ['customer']

    fieldsets = (
        ('Vehicle Information', {
            'fields': ('customer', 'license_plate', 'make', 'model', 'year', 'vin', 'color')
        }),
        ('Maintenance', {
            'fields': ('mileage',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def total_complaints(self, obj):
        """Display total complaints for this car."""
        return obj.total_complaints
    total_complaints.short_description = 'Complaints'
