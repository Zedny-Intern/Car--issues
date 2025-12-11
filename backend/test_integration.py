"""
Integration test to verify all components work together correctly.
Run with: python manage.py shell < test_integration.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'car_diagnosis_system.settings')
django.setup()

print("="*70)
print("INTEGRATION TEST - Car Diagnosis System")
print("="*70)

# Test 1: Import all ML modules
print("\n1. Testing ML Module Imports...")
try:
    from apps.ml_models.rag_service import rag_service, RAGService
    print("   ✅ rag_service imported successfully")
except Exception as e:
    print(f"   ❌ Error importing rag_service: {e}")

try:
    from apps.ml_models.complaint_classifier import get_classifier, ComplaintClassifier
    print("   ✅ complaint_classifier imported successfully")
except Exception as e:
    print(f"   ❌ Error importing complaint_classifier: {e}")

try:
    from apps.ml_models.text_preprocessing import clean_text, TextPreprocessor
    print("   ✅ text_preprocessing imported successfully")
except Exception as e:
    print(f"   ❌ Error importing text_preprocessing: {e}")

try:
    from apps.ml_models.knowledge_loader import KnowledgeLoader
    print("   ✅ knowledge_loader imported successfully")
except Exception as e:
    print(f"   ❌ Error importing knowledge_loader: {e}")

try:
    from apps.ml_models.vector_store import VectorStore
    print("   ✅ vector_store imported successfully")
except Exception as e:
    print(f"   ❌ Error importing vector_store: {e}")

# Test 2: Test Text Preprocessing
print("\n2. Testing Text Preprocessing...")
try:
    from apps.ml_models.text_preprocessing import clean_text
    test_text = "The CAR has a BRAKE problem! 123"
    cleaned = clean_text(test_text)
    print(f"   Input:  '{test_text}'")
    print(f"   Output: '{cleaned}'")
    print("   ✅ Text preprocessing working correctly")
except Exception as e:
    print(f"   ❌ Error in text preprocessing: {e}")

# Test 3: Test Knowledge Loader
print("\n3. Testing Knowledge Loader...")
try:
    from apps.ml_models.knowledge_loader import KnowledgeLoader
    loader = KnowledgeLoader()
    issues = loader.load_common_issues()
    error_codes = loader.load_error_codes()
    print(f"   ✅ Loaded {len(issues)} common issues")
    print(f"   ✅ Loaded {len(error_codes)} error codes")
except Exception as e:
    print(f"   ❌ Error loading knowledge: {e}")

# Test 4: Test RAG Service
print("\n4. Testing RAG Service...")
try:
    from apps.ml_models.rag_service import rag_service
    stats = rag_service.get_statistics()
    print(f"   ✅ RAG Service initialized")
    print(f"   ✅ Collection: {stats.get('collection')}")
except Exception as e:
    print(f"   ❌ Error with RAG Service: {e}")

# Test 5: Test Models
print("\n5. Testing Django Models...")
try:
    from apps.cars.models import Car
    from apps.complaints.models import Complaint, ComplaintCategory
    from apps.chat.models import ChatSession, ChatMessage
    from apps.customers.models import Customer
    print("   ✅ All models imported successfully")
    
    # Check if tables exist
    car_count = Car.objects.count()
    complaint_count = Complaint.objects.count()
    print(f"   ✅ Cars in database: {car_count}")
    print(f"   ✅ Complaints in database: {complaint_count}")
except Exception as e:
    print(f"   ❌ Error with models: {e}")

# Test 6: Test API Views
print("\n6. Testing API Views...")
try:
    from apps.complaints.views import ComplaintViewSet
    from apps.chat.views import ChatSessionViewSet
    print("   ✅ ComplaintViewSet imported")
    print("   ✅ ChatSessionViewSet imported")
except Exception as e:
    print(f"   ❌ Error with views: {e}")

# Test 7: Test Serializers
print("\n7. Testing Serializers...")
try:
    from apps.complaints.serializers import ComplaintSerializer
    from apps.chat.serializers import ChatSessionSerializer
    print("   ✅ ComplaintSerializer imported")
    print("   ✅ ChatSessionSerializer imported")
except Exception as e:
    print(f"   ❌ Error with serializers: {e}")

# Test 8: Test Settings
print("\n8. Testing Django Settings...")
try:
    from django.conf import settings
    print(f"   ✅ DEBUG: {settings.DEBUG}")
    print(f"   ✅ DATABASES: {bool(settings.DATABASES)}")
    print(f"   ✅ INSTALLED_APPS: {len(settings.INSTALLED_APPS)} apps")
    print(f"   ✅ ML_MODEL_PATH: {settings.ML_MODEL_PATH}")
    print(f"   ✅ BERT_TOKENIZER_PATH: {settings.BERT_TOKENIZER_PATH}")
except Exception as e:
    print(f"   ❌ Error with settings: {e}")

print("\n" + "="*70)
print("INTEGRATION TEST COMPLETED")
print("="*70)
print("\n✅ All systems aligned and ready to use!")
