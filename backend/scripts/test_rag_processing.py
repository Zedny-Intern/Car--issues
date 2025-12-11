import os
import sys
import django
from django.conf import settings
from pathlib import Path

# Setup Django environment
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'car_diagnosis_system.settings')
django.setup()

from apps.ml_models.document_loader import document_loader

def test_rag_processing():
    print("="*50)
    print(" TESTING RAG PROCESSING PIPELINE")
    print("="*50)

    # 1. Create a dummy file
    dummy_path = Path(settings.MEDIA_ROOT) / 'test_doc.txt'
    with open(dummy_path, 'w') as f:
        f.write("This is a test document about car engines. It mentions the BMW E36.")

    print(f"Created dummy file: {dummy_path}")

    # 2. Run processing
    print("\nRunning document_loader.process_file()...")
    try:
        result = document_loader.process_file(str(dummy_path), force=True)
        print(f"\nResult: {result}")
        
        if result.get('success'):
            print("✅ SUCCESS: Document processed and indexed.")
        else:
            print(f"❌ FAILURE: {result.get('error')}")
            
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

    # Cleanup
    if dummy_path.exists():
        os.remove(dummy_path)

if __name__ == "__main__":
    test_rag_processing()
