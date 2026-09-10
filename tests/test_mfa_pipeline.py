import pyotp
import json
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.biometrics.models import FingerprintTemplate
from apps.biometrics.crypto import encrypt_template, decrypt_template
from .sample_minutiae import TEMPLATE_VOTER_1

class MFAPipelineTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.matric_no = "20/54321U/1"
        self.password = "VoterPass123!"
        self.user = User.objects.create_user(
            username=self.matric_no,
            matric_no=self.matric_no,
            password=self.password,
            first_name="Chukwuma",
            last_name="Okonkwo",
            faculty="Faculty of Science",
            department="Computer Science",
            level=400,
            is_verified=True
        )

        self.totp_secret = self.user.ensure_totp_secret()
        
        # Enroll AES Encrypted Biometric Template
        self.template_obj = FingerprintTemplate.objects.create(
            user=self.user,
            finger_index=FingerprintTemplate.FINGER_RIGHT_INDEX
        )
        self.template_obj.set_template_data(TEMPLATE_VOTER_1)
        self.template_obj.save()
        self.user.biometric_enrolled = True
        self.user.save()

    def test_step1_password_success(self):
        """Test Stage 1 authenticates valid password and advances session."""
        response = self.client.post(reverse('accounts:login_step1'), {
            'matric_no': self.matric_no,
            'password': self.password
        })
        self.assertRedirects(response, reverse('accounts:login_step2_otp'))
        self.assertEqual(self.client.session.get('mfa_step'), 'STAGE1_PASSWORD_PASSED')
        self.assertEqual(self.client.session.get('mfa_user_id'), self.user.id)

    def test_step1_password_failure(self):
        """Test Stage 1 rejects invalid password and increments failed attempts."""
        response = self.client.post(reverse('accounts:login_step1'), {
            'matric_no': self.matric_no,
            'password': 'WrongPassword999!'
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 1)

    def test_step2_otp_success(self):
        """Test Stage 2 accepts valid RFC 6238 TOTP code after Stage 1."""
        # Setup session to simulate Stage 1 passed
        session = self.client.session
        session['mfa_user_id'] = self.user.id
        session['mfa_matric_no'] = self.user.matric_no
        session['mfa_step'] = 'STAGE1_PASSWORD_PASSED'
        session.save()

        # Generate valid TOTP code
        current_otp = pyotp.TOTP(self.totp_secret).now()

        response = self.client.post(reverse('accounts:login_step2_otp'), {
            'otp_code': current_otp
        })
        self.assertRedirects(response, reverse('accounts:login_step3_biometric'))
        self.assertEqual(self.client.session.get('mfa_step'), 'STAGE2_OTP_PASSED')

    def test_step2_otp_failure(self):
        """Test Stage 2 rejects invalid OTP code."""
        session = self.client.session
        session['mfa_user_id'] = self.user.id
        session['mfa_matric_no'] = self.user.matric_no
        session['mfa_step'] = 'STAGE1_PASSWORD_PASSED'
        session.save()

        response = self.client.post(reverse('accounts:login_step2_otp'), {
            'otp_code': '000000'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get('mfa_step'), 'STAGE1_PASSWORD_PASSED')

    def test_step3_biometric_success(self):
        """Test Stage 3 SourceAFIS minutiae matching completes full login."""
        session = self.client.session
        session['mfa_user_id'] = self.user.id
        session['mfa_matric_no'] = self.user.matric_no
        session['mfa_step'] = 'STAGE2_OTP_PASSED'
        session.save()

        # Send probe template matching enrolled voter 1
        response = self.client.post(
            reverse('accounts:verify_biometric_ajax'),
            data=json.dumps({'probe_template': TEMPLATE_VOTER_1}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['score'], 40.0)
        self.assertEqual(self.client.session.get('mfa_step'), 'AUTHENTICATED')
