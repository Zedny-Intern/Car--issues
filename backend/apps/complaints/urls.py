"""
URL configuration for Complaint API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ComplaintViewSet, quick_submit_complaint

router = DefaultRouter()
router.register(r'', ComplaintViewSet, basename='complaint')

urlpatterns = [
    path('quick-submit/', quick_submit_complaint, name='quick-submit-complaint'),
    path('', include(router.urls)),
]
