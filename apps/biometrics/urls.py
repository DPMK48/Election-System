from django.urls import path
from . import views

app_name = 'biometrics'

urlpatterns = [
    path('api/enroll/', views.enroll_fingerprint_api, name='enroll_api'),
    path('benchmark/', views.benchmark_far_frr_view, name='benchmark'),
]
