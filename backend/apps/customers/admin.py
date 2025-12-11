"""
Admin configuration for Customer model.
"""
from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Admin interface for Customer model."""
    list_display = ['name', 'email', 'phone', 'total_cars', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'email', 'phone']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Personal Information', {
            'fields': ('name', 'email', 'phone', 'address')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def total_cars(self, obj):
        """Display total cars for this customer."""
        return obj.total_cars
    total_cars.short_description = 'Total Cars'
