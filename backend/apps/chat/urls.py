"""
URL configuration for Chat API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChatSessionViewSet, ChatMessageViewSet

router = DefaultRouter()
router.register(r'sessions', ChatSessionViewSet, basename='chat-session')
router.register(r'messages', ChatMessageViewSet, basename='chat-message')

urlpatterns = [
    path('', include(router.urls)),
]
