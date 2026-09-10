from django.urls import path
from . import views
from . import webauthn_views

app_name = 'accounts'

urlpatterns = [
    path('login/step1/', views.login_step1_password, name='login_step1'),
    path('login/step2/', views.login_step2_otp, name='login_step2_otp'),
    path('login/step3/', views.login_step3_biometric, name='login_step3_biometric'),
    path('login/step3/verify-ajax/', views.verify_biometric_ajax, name='verify_biometric_ajax'),
    path('register/', views.register_voter, name='register'),
    path('enroll-fingerprint/', views.enroll_fingerprint_view, name='enroll_fingerprint'),
    path('enroll-mfa/', views.enroll_mfa_view, name='enroll_mfa'),
    path('enroll-mfa/<int:user_id>/', views.enroll_mfa_view, name='enroll_mfa_user'),
    path('access-denied/', views.access_denied, name='access_denied'),
    path('logout/', views.logout_view, name='logout'),

    # WebAuthn (FIDO2 Device Fingerprint) endpoints
    path('webauthn/register/options/', webauthn_views.webauthn_register_options, name='webauthn_register_options'),
    path('webauthn/register/verify/', webauthn_views.webauthn_register_verify, name='webauthn_register_verify'),
    path('webauthn/auth/options/', webauthn_views.webauthn_auth_options, name='webauthn_auth_options'),
    path('webauthn/auth/verify/', webauthn_views.webauthn_auth_verify, name='webauthn_auth_verify'),
]
