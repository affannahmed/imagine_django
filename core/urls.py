from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from django.http import HttpResponse

def root_endpoint(request):
    """Returns server URL for cPanel discovery"""
    return HttpResponse("http://44.222.48.230:8000/")

urlpatterns = [
    # Root endpoint MUST be first!
    path('', root_endpoint, name='root'),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # App URLs
    path('', include('pixverse.urls')),
    path('imagemodels/', include('imagemodels.urls')),
    path('assets/', include('AssetsImagine.urls')),
]

# Always serve media/static in production
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)