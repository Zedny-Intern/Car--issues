import os
import django
import sys
from pathlib import Path

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'car_diagnosis_system.settings')
django.setup()

from apps.ml_models.document_loader import document_loader

def check_status():
    print("Checking RAG Status...")
    stats = document_loader.get_statistics()
    print("\n--- Statistics ---")
    for k, v in stats.items():
        print(f"{k}: {v}")
    
    print("\n--- Indexed Files ---")
    from apps.complaints.models import ComplaintDocument
    from apps.ml_models.models import DocumentMetadata
    
    docs = DocumentMetadata.objects.all()
    for d in docs:
        print(f"- {d.file_name} (Indexed: {d.indexed}, Chunks: {d.chunks.count()})")

if __name__ == "__main__":
    check_status()
