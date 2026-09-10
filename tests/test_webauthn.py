import json
import base64
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.biometrics.models import WebAuthnCredential

User = get_user_model()

class WebAuthnTestCase(TestCase):
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

    def test_credential_model_str(self):
        """Test WebAuthnCredential model fields and string representation."""
        cred = WebAuthnCredential.objects.create(
            user=self.user,
            credential_id="test_cred_id_12345",
            public_key="test_public_key_67890",
            sign_count=0,
            device_name="Samsung Galaxy S23 Fingerprint"
        )
        self.assertIn("20/54321U/1", str(cred))
        self.assertIn("Samsung Galaxy S23 Fingerprint", str(cred))
        self.assertTrue(cred.is_active)

    def test_register_options_unauthenticated_no_session(self):
        """Test registration options rejects unauthenticated requests with no session."""
        response = self.client.post(
            reverse('accounts:webauthn_register_options'),
            data=json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertFalse(data['success'])

    def test_register_options_with_session(self):
        """Test registration options succeeds when user is stored in session during onboarding."""
        session = self.client.session
        session['webauthn_enroll_user_id'] = self.user.id
        session['webauthn_enroll_matric'] = self.user.matric_no
        session.save()

        response = self.client.post(
            reverse('accounts:webauthn_register_options'),
            data=json.dumps({'device_name': "Pixel 8 Pro"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('challenge', data)
        self.assertIn('rp', data)
        self.assertEqual(data['rp']['id'], 'localhost')
        self.assertIn('user', data)
        self.assertEqual(data['user']['name'], self.matric_no)
        # Verify challenge was saved in session
        self.assertEqual(self.client.session.get('webauthn_register_challenge'), data['challenge'])

    def test_auth_options_requires_stage2_otp(self):
        """Test authentication options returns 403 if user hasn't passed Stage 2 OTP."""
        response = self.client.post(
            reverse('accounts:webauthn_auth_options'),
            data=json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)

    def test_auth_options_no_credential_returns_400(self):
        """Test auth options returns error if user has no registered WebAuthn credentials."""
        session = self.client.session
        session['mfa_user_id'] = self.user.id
        session['mfa_matric_no'] = self.user.matric_no
        session['mfa_step'] = 'STAGE2_OTP_PASSED'
        session.save()

        response = self.client.post(
            reverse('accounts:webauthn_auth_options'),
            data=json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('No device fingerprint registered', data['message'])

    def test_auth_options_with_credential(self):
        """Test auth options generates valid challenge and allowCredentials list."""
        # Create a valid credential for user
        dummy_cred_id = base64.urlsafe_b64encode(b"dummy_credential_id_bytes_12345").decode('utf-8').rstrip('=')
        WebAuthnCredential.objects.create(
            user=self.user,
            credential_id=dummy_cred_id,
            public_key="dummy_key",
            sign_count=0,
            device_name="MacBook Touch ID"
        )

        session = self.client.session
        session['mfa_user_id'] = self.user.id
        session['mfa_matric_no'] = self.user.matric_no
        session['mfa_step'] = 'STAGE2_OTP_PASSED'
        session.save()

        response = self.client.post(
            reverse('accounts:webauthn_auth_options'),
            data=json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('challenge', data)
        self.assertIn('allowCredentials', data)
        self.assertEqual(len(data['allowCredentials']), 1)
        self.assertEqual(data['allowCredentials'][0]['id'], dummy_cred_id)
        self.assertEqual(self.client.session.get('webauthn_auth_challenge'), data['challenge'])

    def test_enroll_fingerprint_view(self):
        """Test enrollment page renders properly with user in session."""
        session = self.client.session
        session['webauthn_enroll_user_id'] = self.user.id
        session['webauthn_enroll_matric'] = self.user.matric_no
        session.save()

        response = self.client.get(reverse('accounts:enroll_fingerprint'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Register Device Fingerprint")
        self.assertContains(response, self.matric_no)
