import json
import pyotp
import qrcode
import io
import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings

from .forms import PasswordAuthForm, OTPAuthForm, VoterRegistrationForm
from apps.audit.ledger import log_audit_event
from apps.audit.models import AuditLog
from apps.biometrics.models import FingerprintTemplate
from apps.biometrics.matching import match_minutiae_templates

User = get_user_model()
MAX_LOGIN_ATTEMPTS = 5

def login_step1_password(request):
    """
    Stage 1: Knowledge Factor (Matriculation ID + Password).
    PBKDF2/bcrypt verification.
    """
    # If already fully authenticated, redirect to dashboard
    if request.user.is_authenticated and request.session.get('mfa_step') == 'AUTHENTICATED':
        return redirect('elections:dashboard')

    form = PasswordAuthForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        matric_no = form.cleaned_data['matric_no'].strip().upper()
        password = form.cleaned_data['password']

        try:
            user = User.objects.get(matric_no__iexact=matric_no)
        except User.DoesNotExist:
            user = None

        if user:
            if user.is_locked:
                log_audit_event(
                    AuditLog.EVENT_LOGIN_STEP1_FAIL,
                    request=request,
                    matric_no=matric_no,
                    details={"reason": "Attempted login on locked account"}
                )
                request.session['denied_reason'] = "Your account has been locked due to excessive failed attempts. Please contact the Electoral Commission."
                return redirect('accounts:access_denied')

            # Authenticate credentials
            if user.check_password(password):
                user.failed_login_attempts = 0
                user.save(update_fields=['failed_login_attempts'])

                # Advance session state
                request.session['mfa_user_id'] = user.id
                request.session['mfa_matric_no'] = user.matric_no
                request.session['mfa_step'] = 'STAGE1_PASSWORD_PASSED'

                log_audit_event(
                    AuditLog.EVENT_LOGIN_STEP1_SUCCESS,
                    request=request,
                    user=user,
                    details={"message": "Stage 1 (Password) authenticated successfully"}
                )

                # Ensure TOTP secret exists
                user.ensure_totp_secret()

                return redirect('accounts:login_step2_otp')
            else:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                    user.is_locked = True
                    user.save(update_fields=['failed_login_attempts', 'is_locked'])
                    log_audit_event(
                        AuditLog.EVENT_SECURITY_LOCKOUT,
                        request=request,
                        user=user,
                        details={"reason": f"Exceeded {MAX_LOGIN_ATTEMPTS} failed password attempts"}
                    )
                    request.session['denied_reason'] = f"Account locked after {MAX_LOGIN_ATTEMPTS} failed attempts."
                    return redirect('accounts:access_denied')
                else:
                    user.save(update_fields=['failed_login_attempts'])
                    remaining = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
                    messages.error(request, f"Invalid password. {remaining} attempt(s) remaining before lockout.")
                    log_audit_event(
                        AuditLog.EVENT_LOGIN_STEP1_FAIL,
                        request=request,
                        user=user,
                        details={"attempts": user.failed_login_attempts}
                    )
        else:
            messages.error(request, "Matriculation / Staff ID not found in university voter database.")
            log_audit_event(
                AuditLog.EVENT_LOGIN_STEP1_FAIL,
                request=request,
                matric_no=matric_no,
                details={"reason": "User not found"}
            )

    return render(request, 'accounts/login_step1_password.html', {'form': form})


def login_step2_otp(request):
    """
    Stage 2: Possession Factor (RFC 6238 TOTP).
    Enforces that Stage 1 was successfully completed in this session.
    """
    # Strict sequential session guard
    if request.session.get('mfa_step') != 'STAGE1_PASSWORD_PASSED':
        log_audit_event(
            AuditLog.EVENT_STAGE_SKIP_BLOCKED,
            request=request,
            matric_no=request.session.get('mfa_matric_no'),
            details={"attempted_step": "STAGE 2 (OTP)", "actual_state": request.session.get('mfa_step')}
        )
        request.session['denied_reason'] = "Security Violation: You must complete Stage 1 (Password) before accessing Stage 2."
        return redirect('accounts:access_denied')

    user_id = request.session.get('mfa_user_id')
    user = get_object_or_404(User, id=user_id)

    form = OTPAuthForm(request.POST or None)
    
    # Generate live current demo OTP code for convenient testing on terminal
    totp = pyotp.TOTP(user.totp_secret)
    current_otp = totp.now()

    if request.method == 'POST' and form.is_valid():
        entered_code = form.cleaned_data['otp_code'].strip()

        if user.verify_totp(entered_code, valid_window=settings.OTP_VALID_WINDOW):
            request.session['mfa_step'] = 'STAGE2_OTP_PASSED'
            log_audit_event(
                AuditLog.EVENT_LOGIN_STEP2_SUCCESS,
                request=request,
                user=user,
                details={"message": "Stage 2 (OTP) verified successfully"}
            )
            return redirect('accounts:login_step3_biometric')
        else:
            messages.error(request, "Invalid or expired OTP code. Please check your authenticator or generate a new code.")
            log_audit_event(
                AuditLog.EVENT_LOGIN_STEP2_FAIL,
                request=request,
                user=user,
                details={"entered_code": entered_code}
            )

    return render(request, 'accounts/login_step2_otp.html', {
        'form': form,
        'user_obj': user,
        'demo_otp': current_otp
    })


def login_step3_biometric(request):
    """
    Stage 3: Inherence Factor (WebAuthn Device Fingerprint Verification).
    Enforces that Stage 1 and Stage 2 were completed in this session.
    """
    if request.session.get('mfa_step') != 'STAGE2_OTP_PASSED':
        log_audit_event(
            AuditLog.EVENT_STAGE_SKIP_BLOCKED,
            request=request,
            matric_no=request.session.get('mfa_matric_no'),
            details={"attempted_step": "STAGE 3 (BIOMETRIC)", "actual_state": request.session.get('mfa_step')}
        )
        request.session['denied_reason'] = "Security Violation: You must pass Stage 1 & 2 before biometric authentication."
        return redirect('accounts:access_denied')

    user_id = request.session.get('mfa_user_id')
    user = get_object_or_404(User, id=user_id)

    # Check if user has registered WebAuthn credentials (device fingerprint)
    from apps.biometrics.models import WebAuthnCredential
    has_credential = WebAuthnCredential.objects.filter(user=user, is_active=True).exists()

    return render(request, 'accounts/login_step3_biometric.html', {
        'user_obj': user,
        'has_credential': has_credential,
    })


@require_POST
def verify_biometric_ajax(request):
    """
    AJAX endpoint for Stage 3 Biometric Minutiae verification.
    Receives probe minutiae template from polling terminal / capture agent,
    decrypts enrolled template with AES-256 GCM, and executes SourceAFIS matching.
    """
    if request.session.get('mfa_step') != 'STAGE2_OTP_PASSED':
        return JsonResponse({'success': False, 'message': 'Invalid authentication session state.'}, status=403)

    user_id = request.session.get('mfa_user_id')
    user = get_object_or_404(User, id=user_id)

    try:
        data = json.loads(request.body.decode('utf-8'))
        probe_template = data.get('probe_template', {})
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid minutiae template payload.'}, status=400)

    if not hasattr(user, 'fingerprint_template') or not user.fingerprint_template:
        return JsonResponse({
            'success': False,
            'message': 'No biometric fingerprint enrolled for this voter. Please visit Electoral Officer for enrollment.'
        }, status=400)

    # Decrypt reference template from database with AES-256
    try:
        reference_template = user.fingerprint_template.get_template_data()
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Biometric template decryption failure: {str(e)}'
        }, status=500)

    # Perform SourceAFIS minutiae matching
    match_result = match_minutiae_templates(probe_template, reference_template)

    if match_result['is_match']:
        # Full 3-Factor Authentication Complete!
        request.session['mfa_step'] = 'AUTHENTICATED'
        login(request, user)

        log_audit_event(
            AuditLog.EVENT_BIOMETRIC_MATCH_SUCCESS,
            request=request,
            user=user,
            details={
                "score": match_result['similarity_score'],
                "matched_points": match_result['matched_minutiae_count'],
                "confidence": match_result['confidence']
            }
        )

        redirect_url = '/elections/dashboard/'
        if user.is_admin_or_officer():
            redirect_url = '/elections/admin/command-center/'

        return JsonResponse({
            'success': True,
            'score': match_result['similarity_score'],
            'confidence': match_result['confidence'],
            'redirect_url': redirect_url
        })
    else:
        log_audit_event(
            AuditLog.EVENT_BIOMETRIC_MATCH_FAIL,
            request=request,
            user=user,
            details={
                "score": match_result['similarity_score'],
                "matched_points": match_result['matched_minutiae_count'],
                "confidence": match_result['confidence']
            }
        )
        return JsonResponse({
            'success': False,
            'score': match_result['similarity_score'],
            'confidence': match_result['confidence'],
            'message': f"Biometric Minutiae Mismatch! Similarity score ({match_result['similarity_score']}%) fell below required threshold (40.0%)."
        }, status=401)


def register_voter(request):
    """Voter onboarding and registration."""
    form = VoterRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.username = user.matric_no
        user.role = User.ROLE_VOTER
        user.set_password(form.cleaned_data['password'])
        user.save()
        user.ensure_totp_secret()

        log_audit_event(
            AuditLog.EVENT_ADMIN_ACTION,
            request=request,
            user=user,
            details={"action": "Voter registered into electoral registry"}
        )

        # Store user ID in session for fingerprint enrollment
        request.session['webauthn_enroll_user_id'] = user.id
        request.session['webauthn_enroll_matric'] = user.matric_no
        messages.success(request, f"Account created for {user.matric_no}! Now register your device fingerprint.")
        return redirect('accounts:enroll_fingerprint')

    return render(request, 'accounts/register_voter.html', {'form': form})


def enroll_fingerprint_view(request):
    """
    Post-registration page where students enroll their device's fingerprint
    using WebAuthn. Can also be accessed independently.
    """
    user_id = request.session.get('webauthn_enroll_user_id')
    matric_no = request.session.get('webauthn_enroll_matric', '')

    if not user_id:
        if request.user.is_authenticated:
            user_id = request.user.id
            matric_no = request.user.matric_no
        else:
            messages.warning(request, "Please register or log in first.")
            return redirect('accounts:register')

    user = get_object_or_404(User, id=user_id)
    from apps.biometrics.models import WebAuthnCredential
    credentials = WebAuthnCredential.objects.filter(user=user, is_active=True)

    return render(request, 'accounts/enroll_fingerprint.html', {
        'target_user': user,
        'credentials': credentials,
    })


def enroll_mfa_view(request, user_id=None):
    """
    Electoral Officer / Admin setup view to enroll TOTP and Biometrics for a voter.
    """
    target_user = get_object_or_404(User, id=user_id) if user_id else request.user
    if not target_user.is_authenticated:
        return redirect('accounts:login_step1')

    secret = target_user.ensure_totp_secret()
    uri = target_user.get_totp_uri()

    # Generate QR Code image in memory as Base64
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    qr_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    return render(request, 'accounts/enroll_mfa.html', {
        'target_user': target_user,
        'secret': secret,
        'qr_b64': qr_b64,
        'totp_code': pyotp.TOTP(secret).now()
    })


def access_denied(request):
    """Shared Access-Denied & Security Violation landing page."""
    reason = request.session.pop('denied_reason', "Access Denied: Unverified or unauthorized session state.")
    return render(request, 'accounts/access_denied.html', {'reason': reason})


def logout_view(request):
    """Clears session, logs event, and routes back to Step 1."""
    if request.user.is_authenticated:
        log_audit_event(
            AuditLog.EVENT_ADMIN_ACTION if request.user.is_admin_or_officer() else AuditLog.EVENT_LOGIN_STEP1_SUCCESS,
            request=request,
            user=request.user,
            details={"action": "User logged out"}
        )
    logout(request)
    request.session.flush()
    messages.info(request, "You have been safely logged out of the voting terminal.")
    return redirect('accounts:login_step1')
