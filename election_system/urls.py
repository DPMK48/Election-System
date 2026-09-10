from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('accounts:login_step1')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('biometrics/', include('apps.biometrics.urls', namespace='biometrics')),
    path('elections/', include('apps.elections.urls', namespace='elections')),
    path('audit/', include('apps.audit.urls', namespace='audit')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
