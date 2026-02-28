"""
URL configuration for Car Diagnosis System.
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

schema_permissions = [permissions.AllowAny] if settings.DEBUG else [permissions.IsAuthenticated]

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
    permission_classes=schema_permissions,
)

urlpatterns = [
    path('healthz', lambda request: JsonResponse({'status': 'ok'}), name='healthz'),

    # Admin panel
    path('admin/', admin.site.urls),

    # Auth endpoints
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # API endpoints
    path('api/v1/customers/', include('apps.customers.urls')),
    path('api/v1/cars/', include('apps.cars.urls')),
    path('api/v1/complaints/', include('apps.complaints.urls')),
    path('api/v1/chat/', include('apps.chat.urls')),
    
    # Multi-modal RAG endpoints
    path('api/v1/ml/', include('apps.ml_models.urls')),
]

if settings.DEBUG:
    urlpatterns += [
        # API Documentation (development only)
        path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    ]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
