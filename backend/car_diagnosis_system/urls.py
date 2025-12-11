"""
URL configuration for Car Diagnosis System.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Swagger/OpenAPI documentation
schema_view = get_schema_view(
    openapi.Info(
        title="Car Diagnosis System API",
        default_version='v1',
        description="AI-powered car complaint diagnosis and chat system",
        contact=openapi.Contact(email="support@cardiagnosis.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # Admin panel
    path('admin/', admin.site.urls),

    # API Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # API endpoints
    path('api/v1/customers/', include('apps.customers.urls')),
    path('api/v1/cars/', include('apps.cars.urls')),
    path('api/v1/complaints/', include('apps.complaints.urls')),
    path('api/v1/chat/', include('apps.chat.urls')),
    
    # Multi-modal RAG endpoints
    path('api/v1/ml/', include('apps.ml_models.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
