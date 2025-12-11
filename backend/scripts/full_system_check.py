import os
import sys
import django
import requests
from django.conf import settings
from pathlib import Path

# Setup Django environment
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'car_diagnosis_system.settings')
django.setup()

from apps.complaints.models import Complaint, ComplaintDocument
from apps.cars.models import Car

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def check_django_settings():
    print_header("1. DJANGO SETTINGS")
    print(f"DEBUG Mode: {settings.DEBUG}")
    print(f"Database Name: {settings.DATABASES['default']['NAME']}")
    print(f"Database Host: {settings.DATABASES['default']['HOST']}")
    print(f"Media Root: {settings.MEDIA_ROOT}")
    print(f"Ollama URL: {getattr(settings, 'OLLAMA_BASE_URL', 'Not Set')}")
    print(f"Ollama Model: {getattr(settings, 'OLLAMA_TEXT_MODEL', 'Not Set')}")

def check_database():
    print_header("2. DATABASE CONNECTIVITY")
    try:
        car_count = Car.objects.count()
        complaint_count = Complaint.objects.count()
        doc_count = ComplaintDocument.objects.count()
        
        print(f"✅ Connection Successful")
        print(f"   - Cars: {car_count}")
        print(f"   - Complaints: {complaint_count}")
        print(f"   - Documents: {doc_count}")
    except Exception as e:
        print(f"❌ Database Error: {e}")

def check_storage():
    print_header("3. FILE STORAGE")
    media_root = Path(settings.MEDIA_ROOT)
    
    if media_root.exists():
        print(f"✅ MEDIA_ROOT exists: {media_root}")
        
        # Check specific folders
        docs_dir = media_root / 'complaint_docs'
        if docs_dir.exists():
            print(f"✅ 'complaint_docs' directory exists")
            files = list(docs_dir.glob('**/*.*'))
            print(f"   - Found {len(files)} files in storage")
        else:
            print(f"⚠️ 'complaint_docs' directory missing (created on first upload)")
    else:
        print(f"❌ MEDIA_ROOT missing: {media_root}")

def check_rag_dependencies():
    print_header("4. RAG / EMBEDDINGS (Sentence Transformers)")
    try:
        import sentence_transformers
        print(f"✅ sentence-transformers installed: {sentence_transformers.__version__}")
        
        from langchain_huggingface import HuggingFaceEmbeddings
        print("✅ langchain-huggingface installed")
        
        print("   - Attempting to load model (lightweight check)...")
        # Just checking if the module can be initialized without error
        try:
            # We don't want to download the model here if large, but checking import is good
             from langchain_community.embeddings import HuggingFaceEmbeddings as CommunityEmbeddings
             print("   ✅ langchain-community embeddings available")
        except Exception as e:
             print(f"   ⚠️ Warning loading community embeddings: {e}")

    except ImportError as e:
        print(f"❌ Missing Dependency: {e}")
    except Exception as e:
        print(f"❌ unexpected error in RAG check: {e}")

def check_ollama():
    print_header("5. AI MODEL (Ollama)")
    base_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
    model = getattr(settings, 'OLLAMA_TEXT_MODEL', 'llama3')
    
    print(f"Target: {base_url}")
    print(f"Model: {model}")
    
    try:
        # Version
        resp = requests.get(f"{base_url}/api/version", timeout=3)
        if resp.status_code == 200:
            print(f"✅ Connected to Ollama (v{resp.json().get('version')})")
        else:
            print(f"⚠️ Connected but returned status {resp.status_code}")
            return

        # Model presence
        resp = requests.get(f"{base_url}/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m.get('name') for m in resp.json().get('models', [])]
            if model in models:
                print(f"✅ Model '{model}' is loaded and available")
            else:
                print(f"❌ Model '{model}' NOT found in Ollama list: {models}")
                print(f"   PLEASE RUN: ollama pull {model}")
        
        # Simple Generation
        print("   - Testing generation...")
        try:
            r = requests.post(f"{base_url}/api/generate", json={
                "model": model,
                "prompt": "Hi",
                "stream": False
            }, timeout=10)
            if r.status_code == 200:
                print("✅ Generation successful")
            else:
                print(f"❌ Generation failed: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"❌ Generation timed out or failed: {e}")

    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Ollama. Check if it is running.")
    except Exception as e:
        print(f"❌ Ollama Check Failed: {e}")

if __name__ == "__main__":
    print("\n🚀 STARTING FULL SYSTEM DIAGNOSTIC")
    check_django_settings()
    check_database()
    check_storage()
    check_rag_dependencies()
    check_ollama()
    print("\n✅ DIAGNOSTIC COMPLETE")
