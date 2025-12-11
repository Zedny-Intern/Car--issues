import os
import sys
import django
from pathlib import Path

# Setup Django environment
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'car_diagnosis_system.settings')
django.setup()

from django.conf import settings
from apps.complaints.models import Complaint, ComplaintDocument

def print_header(title):
    print(f"\n{'='*50}")
    print(f" {title}")
    print(f"{'='*50}")

def verify_database():
    print_header("DATABASE VERIFICATION")
    
    # Check Complaints
    complaint_count = Complaint.objects.count()
    print(f"Total Complaints: {complaint_count}")
    
    if complaint_count > 0:
        latest = Complaint.objects.first()  # Ordering is -created_at
        print(f"Latest Complaint: {latest}")
        print(f"  - Category: {latest.predicted_category}")
        print(f"  - Created: {latest.created_at}")
    
    # Check Documents
    doc_count = ComplaintDocument.objects.count()
    print(f"\nTotal Documents: {doc_count}")
    
    if doc_count > 0:
        latest_doc = ComplaintDocument.objects.first()
        print(f"Latest Document: {latest_doc.file_name}")
        print(f"  - Path: {latest_doc.file.name}")
        print(f"  - Analyzed: {latest_doc.is_analyzed}")
        if latest_doc.analysis_error:
            print(f"  - Error: {latest_doc.analysis_error}")

def verify_storage():
    print_header("STORAGE VERIFICATION")
    
    media_root = Path(settings.MEDIA_ROOT)
    print(f"MEDIA_ROOT: {media_root}")
    
    if not media_root.exists():
        print("❌ MEDIA_ROOT does not exist!")
        return
    
    print("✅ MEDIA_ROOT exists")
    
    # Check subdirectories
    subdirs = ['complaint_docs']
    for subdir in subdirs:
        path = media_root / subdir
        if path.exists():
            print(f"✅ Subdirectory '{subdir}' found")
            try:
                files = list(path.glob('**/*'))
                file_count = len([f for f in files if f.is_file()])
                print(f"   - Contains {file_count} files")
            except Exception as e:
                print(f"   - Error listing files: {e}")
        else:
            print(f"⚠️ Subdirectory '{subdir}' NOT found (might be created on first upload)")

def test_rag_loader():
    print_header("RAG LOADER DIAGNOSTICS")
    try:
        from apps.ml_models.document_loader import document_loader
        print("✅ DocumentLoader imported successfully")
        
        stats = document_loader.get_statistics()
        print("\nRAG Statistics:")
        for k, v in stats.items():
            print(f"  - {k}: {v}")
            
    except Exception as e:
        print(f"❌ Error initializing DocumentLoader: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        verify_database()
        verify_storage()
        test_rag_loader()
        print("\nVerification Complete.")
    except Exception as e:
        print(f"\n❌ Script failed: {e}")
