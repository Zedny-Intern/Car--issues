"""
Admin registration for ml_models app.
"""
from django.contrib import admin
from .models import DocumentMetadata, DocumentChunk


@admin.register(DocumentMetadata)
class DocumentMetadataAdmin(admin.ModelAdmin):
    """Admin for document metadata."""
    
    list_display = ['file_name', 'file_type', 'indexed', 'page_count', 'created_at']
    list_filter = ['file_type', 'indexed', 'created_at']
    search_fields = ['file_name', 'file_path']
    readonly_fields = ['file_hash', 'created_at', 'updated_at', 'indexed_at']
    ordering = ['-created_at']


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    """Admin for document chunks."""
    
    list_display = ['chunk_id', 'document', 'chunk_type', 'page_number', 'created_at']
    list_filter = ['chunk_type', 'created_at']
    search_fields = ['chunk_id', 'content', 'document__file_name']
    raw_id_fields = ['document']
    ordering = ['-created_at']
