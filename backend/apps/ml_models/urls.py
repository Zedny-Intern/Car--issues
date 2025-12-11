"""
URL routing for ml_models app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import DocumentViewSet, RAGQueryViewSet, ImageViewSet

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='documents')
router.register(r'rag', RAGQueryViewSet, basename='rag')
router.register(r'images', ImageViewSet, basename='images')

urlpatterns = [
    path('', include(router.urls)),
]
