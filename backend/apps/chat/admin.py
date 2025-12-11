"""
Admin configuration for Chat models.
"""
from django.contrib import admin
from .models import ChatSession, ChatMessage


class ChatMessageInline(admin.TabularInline):
    """Inline display of chat messages within session."""
    model = ChatMessage
    extra = 0
    readonly_fields = ['role', 'message', 'created_at']
    can_delete = False
    max_num = 0  # Don't allow adding new messages from admin


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """Admin interface for ChatSession model."""
    list_display = [
        'id',
        'title',
        'customer_name',
        'car_license_plate',
        'is_active',
        'total_messages',
        'created_at',
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = [
        'title',
        'complaint__car__license_plate',
        'complaint__car__customer__name',
    ]
    readonly_fields = ['created_at', 'updated_at', 'closed_at', 'total_messages']
    ordering = ['-updated_at']
    inlines = [ChatMessageInline]

    fieldsets = (
        ('Session Information', {
            'fields': ('complaint', 'title', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'closed_at'),
            'classes': ('collapse',)
        }),
    )

    def customer_name(self, obj):
        """Display customer name."""
        return obj.customer.name
    customer_name.short_description = 'Customer'

    def car_license_plate(self, obj):
        """Display car license plate."""
        return obj.car.license_plate
    car_license_plate.short_description = 'License Plate'

    def total_messages(self, obj):
        """Display total messages."""
        return obj.total_messages
    total_messages.short_description = 'Messages'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Admin interface for ChatMessage model."""
    list_display = [
        'id',
        'session',
        'role',
        'message_preview',
        'created_at',
    ]
    list_filter = ['role', 'created_at']
    search_fields = ['message', 'session__title']
    readonly_fields = ['session', 'role', 'message', 'created_at', 'metadata']
    ordering = ['-created_at']

    def message_preview(self, obj):
        """Display message preview."""
        preview = obj.message[:100]
        if len(obj.message) > 100:
            preview += '...'
        return preview
    message_preview.short_description = 'Message'

    def has_add_permission(self, request):
        """Disable adding messages from admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing messages from admin."""
        return False
