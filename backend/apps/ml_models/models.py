"""
Document metadata models for multi-modal RAG pipeline.
Tracks indexed documents, chunks, and their embeddings.
"""
from django.db import models
from django.utils import timezone


class DocumentMetadata(models.Model):
    """Tracks PDF/image documents that have been processed and indexed."""
    
    FILE_TYPES = [
        ('pdf', 'PDF Document'),
        ('image', 'Image File'),
        ('text', 'Text File'),
    ]
    
    file_path = models.CharField(max_length=512, unique=True)
    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64)  # SHA-256 hash
    file_type = models.CharField(max_length=20, choices=FILE_TYPES)
    file_size = models.BigIntegerField(default=0)
    
    # Indexing status
    indexed = models.BooleanField(default=False)
    indexed_at = models.DateTimeField(null=True, blank=True)
    index_error = models.TextField(null=True, blank=True)
    
    # PDF-specific metadata
    page_count = models.IntegerField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'document_metadata'
        ordering = ['-created_at']
        verbose_name = 'Document Metadata'
        verbose_name_plural = 'Document Metadata'
    
    def __str__(self):
        return f"{self.file_name} ({self.file_type})"
    
    def mark_indexed(self):
        """Mark document as successfully indexed."""
        self.indexed = True
        self.indexed_at = timezone.now()
        self.index_error = None
        self.save()
    
    def mark_error(self, error_message: str):
        """Mark document indexing as failed."""
        self.indexed = False
        self.index_error = error_message
        self.save()


class DocumentChunk(models.Model):
    """Individual chunks extracted from documents (text, images, tables)."""
    
    CHUNK_TYPES = [
        ('text', 'Text Content'),
        ('image', 'Image'),
        ('table', 'Table'),
    ]
    
    document = models.ForeignKey(
        DocumentMetadata, 
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    chunk_id = models.CharField(max_length=100, unique=True)
    chunk_type = models.CharField(max_length=20, choices=CHUNK_TYPES)
    page_number = models.IntegerField(default=1)
    
    # Content
    content = models.TextField(null=True, blank=True)  # For text/table
    image_path = models.CharField(max_length=512, null=True, blank=True)  # For images
    caption = models.TextField(null=True, blank=True)  # Image caption
    
    # Vector IDs in FAISS
    text_vector_id = models.CharField(max_length=100, null=True, blank=True)
    image_vector_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'document_chunks'
        ordering = ['document', 'page_number']
        verbose_name = 'Document Chunk'
        verbose_name_plural = 'Document Chunks'
    
    def __str__(self):
        return f"{self.document.file_name} - Page {self.page_number} ({self.chunk_type})"
