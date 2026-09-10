"""
ATBU E-Voting — WebAuthn (FIDO2) Views

Handles server-side WebAuthn registration and authentication ceremonies.
Students use their personal device's built-in fingerprint sensor (or Face ID)
to register and authenticate via the browser's WebAuthn API.
"""

import json
import base64
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.contrib.auth import login, get_user_model
from django.conf import settings
from django.utils import timezone

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    ResidentKeyRequirement,
    AuthenticatorAttachment,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    AuthenticationCredential,
    AuthenticatorAttestationResponse,
    AuthenticatorAssertionResponse,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier

from apps.biometrics.models import WebAuthnCredential
from apps.audit.ledger import log_audit_event
from apps.audit.models import AuditLog

User = get_user_model()


def _get_rp_id(request=None):
    if request:
        host = request.get_host().split(':')[0]
        if host in ('localhost', '127.0.0.1', 'testserver'):
            return getattr(settings, 'WEBAUTHN_RP_ID', 'localhost')
        return host
    return getattr(settings, 'WEBAUTHN_RP_ID', 'localhost')

def _get_rp_name():
    return getattr(settings, 'WEBAUTHN_RP_NAME', 'ATBU E-Voting')

def _get_origin(request=None):
    if request:
        origin_header = request.headers.get('Origin')
        if origin_header:
            return origin_header
        host = request.get_host()
        if host.startswith('127.0.0.1'):
            host = host.replace('127.0.0.1', 'localhost', 1)
        return f"{request.scheme}://{host}"
    return getattr(settings, 'WEBAUTHN_ORIGIN', 'http://localhost:8000')


# ---------- REGISTRATION (Enrollment) ----------

@require_POST
def webauthn_register_options(request):
    """
    Generate WebAuthn registration options for the browser.
    Called when a student wants to enroll their device's fingerprint sensor.
    """
    # Determine the user — either from session (during registration) or authenticated
    user = None
    if request.user.is_authenticated:
        user = request.user
    elif request.session.get('webauthn_enroll_user_id'):
        user = get_object_or_404(User, id=request.session['webauthn_enroll_user_id'])
    elif request.session.get('mfa_user_id'):
        user = get_object_or_404(User, id=request.session['mfa_user_id'])

    if not user:
        return JsonResponse({'success': False, 'message': 'No user session found. Please log in first.'}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        data = {}

    device_name = data.get('device_name', 'Personal Device')
    request.session['webauthn_device_name'] = device_name

    # Get existing credential IDs to prevent re-registration
    existing_creds = WebAuthnCredential.objects.filter(user=user, is_active=True)
    exclude_credentials = []
    for cred in existing_creds:
        exclude_credentials.append(
            PublicKeyCredentialDescriptor(id=base64.urlsafe_b64decode(cred.credential_id + '=='))
        )

    # Generate registration options
    options = generate_registration_options(
        rp_id=_get_rp_id(request),
        rp_name=_get_rp_name(),
        user_id=str(user.id).encode('utf-8'),
        user_name=user.matric_no,
        user_display_name=user.get_full_name() or user.matric_no,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            user_verification=UserVerificationRequirement.REQUIRED,
            resident_key=ResidentKeyRequirement.PREFERRED,
        ),
    )

    # Store challenge in session for verification
    options_json = json.loads(options_to_json(options))
    request.session['webauthn_register_challenge'] = options_json['challenge']
    request.session['webauthn_register_user_id'] = user.id

    return JsonResponse(options_json)


@require_POST
def webauthn_register_verify(request):
    """
    Verify the WebAuthn registration response from the browser.
    Stores the public key credential in the database.
    """
    user_id = request.session.get('webauthn_register_user_id')
    challenge = request.session.get('webauthn_register_challenge')

    if not user_id or not challenge:
        return JsonResponse({'success': False, 'message': 'Registration session expired. Please try again.'}, status=400)

    user = get_object_or_404(User, id=user_id)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid request data.'}, status=400)

    credential_id_b64 = data.get('credential_id', '')
    client_data_b64 = data.get('client_data', '')
    attestation_b64 = data.get('attestation_object', '')
    device_name = data.get('device_name', request.session.get('webauthn_device_name', 'Personal Device'))

    try:
        # Build the RegistrationCredential object from the browser response
        reg_credential = RegistrationCredential(
            id=credential_id_b64,
            raw_id=base64.urlsafe_b64decode(credential_id_b64 + '=='),
            response=AuthenticatorAttestationResponse(
                client_data_json=base64.urlsafe_b64decode(client_data_b64 + '=='),
                attestation_object=base64.urlsafe_b64decode(attestation_b64 + '=='),
            ),
            type='public-key',
        )

        # Verify the registration with py-webauthn
        verification = verify_registration_response(
            credential=reg_credential,
            expected_challenge=base64.urlsafe_b64decode(challenge + '=='),
            expected_rp_id=_get_rp_id(request),
            expected_origin=_get_origin(request),
            require_user_verification=True,
        )

        # Store the credential in database
        WebAuthnCredential.objects.create(
            user=user,
            credential_id=credential_id_b64,
            public_key=base64.urlsafe_b64encode(verification.credential_public_key).decode('utf-8').rstrip('='),
            sign_count=verification.sign_count,
            device_name=device_name,
        )

        # Update user biometric enrollment status
        user.biometric_enrolled = True
        user.save(update_fields=['biometric_enrolled'])

        # Audit log
        log_audit_event(
            AuditLog.EVENT_WEBAUTHN_REGISTER,
            request=request,
            user=user,
            details={
                'device_name': device_name,
                'credential_id_prefix': credential_id_b64[:16] + '...',
            }
        )

        # Clear registration session data
        for key in ['webauthn_register_challenge', 'webauthn_register_user_id', 'webauthn_device_name']:
            request.session.pop(key, None)

        return JsonResponse({
            'success': True,
            'message': f'Device fingerprint registered successfully for {user.matric_no}.',
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Registration verification failed: {str(e)}'
        }, status=400)


# ---------- AUTHENTICATION (Login Step 3) ----------

@require_POST
def webauthn_auth_options(request):
    """
    Generate WebAuthn authentication options for the browser.
    Called during login Step 3 to verify fingerprint.
    """
    if request.session.get('mfa_step') != 'STAGE2_OTP_PASSED':
        return JsonResponse({'success': False, 'message': 'Complete Step 1 and Step 2 first.'}, status=403)

    user_id = request.session.get('mfa_user_id')
    user = get_object_or_404(User, id=user_id)

    # Get user's registered credentials
    credentials = WebAuthnCredential.objects.filter(user=user, is_active=True)
    if not credentials.exists():
        return JsonResponse({
            'success': False,
            'message': 'No device fingerprint registered. Please enroll your device first.'
        }, status=400)

    allow_credentials = []
    for cred in credentials:
        allow_credentials.append(
            PublicKeyCredentialDescriptor(id=base64.urlsafe_b64decode(cred.credential_id + '=='))
        )

    options = generate_authentication_options(
        rp_id=_get_rp_id(request),
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    options_json = json.loads(options_to_json(options))
    request.session['webauthn_auth_challenge'] = options_json['challenge']

    return JsonResponse(options_json)


@require_POST
def webauthn_auth_verify(request):
    """
    Verify the WebAuthn authentication response from the browser.
    Completes Stage 3 (Biometric) of the MFA flow.
    """
    if request.session.get('mfa_step') != 'STAGE2_OTP_PASSED':
        return JsonResponse({'success': False, 'message': 'Invalid authentication session state.'}, status=403)

    challenge = request.session.get('webauthn_auth_challenge')
    if not challenge:
        return JsonResponse({'success': False, 'message': 'Authentication session expired.'}, status=400)

    user_id = request.session.get('mfa_user_id')
    user = get_object_or_404(User, id=user_id)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid request data.'}, status=400)

    credential_id_b64 = data.get('credential_id', '')
    client_data_b64 = data.get('client_data', '')
    authenticator_data_b64 = data.get('authenticator_data', '')
    signature_b64 = data.get('signature', '')

    # Find the matching stored credential
    try:
        stored_cred = WebAuthnCredential.objects.get(
            credential_id=credential_id_b64,
            user=user,
            is_active=True
        )
    except WebAuthnCredential.DoesNotExist:
        log_audit_event(
            AuditLog.EVENT_WEBAUTHN_AUTH_FAIL,
            request=request,
            user=user,
            details={'reason': 'Credential ID not found for this user'}
        )
        return JsonResponse({'success': False, 'message': 'Unknown device credential.'}, status=401)

    try:
        # Build the AuthenticationCredential from browser response
        auth_credential = AuthenticationCredential(
            id=credential_id_b64,
            raw_id=base64.urlsafe_b64decode(credential_id_b64 + '=='),
            response=AuthenticatorAssertionResponse(
                client_data_json=base64.urlsafe_b64decode(client_data_b64 + '=='),
                authenticator_data=base64.urlsafe_b64decode(authenticator_data_b64 + '=='),
                signature=base64.urlsafe_b64decode(signature_b64 + '=='),
            ),
            type='public-key',
        )

        # Verify the authentication assertion
        verification = verify_authentication_response(
            credential=auth_credential,
            expected_challenge=base64.urlsafe_b64decode(challenge + '=='),
            expected_rp_id=_get_rp_id(request),
            expected_origin=_get_origin(request),
            credential_public_key=base64.urlsafe_b64decode(stored_cred.public_key + '=='),
            credential_current_sign_count=stored_cred.sign_count,
            require_user_verification=True,
        )

        # Update sign count for replay attack protection
        stored_cred.sign_count = verification.new_sign_count
        stored_cred.last_used_at = timezone.now()
        stored_cred.save(update_fields=['sign_count', 'last_used_at'])

        # Complete 3-Factor Authentication!
        request.session['mfa_step'] = 'AUTHENTICATED'
        login(request, user)

        # Audit log
        log_audit_event(
            AuditLog.EVENT_WEBAUTHN_AUTH_SUCCESS,
            request=request,
            user=user,
            details={
                'device_name': stored_cred.device_name,
                'sign_count': verification.new_sign_count,
            }
        )

        # Clear auth session data
        request.session.pop('webauthn_auth_challenge', None)

        redirect_url = '/elections/dashboard/'
        if user.is_admin_or_officer():
            redirect_url = '/elections/admin/command-center/'

        return JsonResponse({
            'success': True,
            'redirect_url': redirect_url,
            'device_name': stored_cred.device_name,
        })

    except Exception as e:
        log_audit_event(
            AuditLog.EVENT_WEBAUTHN_AUTH_FAIL,
            request=request,
            user=user,
            details={'error': str(e)}
        )
        return JsonResponse({
            'success': False,
            'message': f'Fingerprint verification failed: {str(e)}'
        }, status=401)
