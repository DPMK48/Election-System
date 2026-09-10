from django.test import TestCase
from apps.accounts.models import User
from apps.biometrics.models import FingerprintTemplate
from apps.biometrics.crypto import encrypt_template, decrypt_template
from apps.biometrics.matching import match_minutiae_templates, evaluate_far_frr
from .sample_minutiae import (
    TEMPLATE_VOTER_1,
    TEMPLATE_VOTER_2,
    TEMPLATE_IMPOSTOR,
    generate_synthetic_fingerprint_template
)

class BiometricsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="FUST/2022/CSC/042",
            matric_no="FUST/2022/CSC/042",
            password="VoterPass123!"
        )

    def test_aes_encryption_at_rest(self):
        """Test that biometric templates are encrypted at rest with AES-256 GCM."""
        enc = encrypt_template(TEMPLATE_VOTER_1)
        self.assertIn('ciphertext_b64', enc)
        self.assertIn('nonce_b64', enc)
        self.assertIn('tag_b64', enc)

        # Ciphertext should not contain plaintext JSON strings
        self.assertNotIn('minutiae', enc['ciphertext_b64'])

        # Decryption should return exact original structure
        dec = decrypt_template(enc['ciphertext_b64'], enc['nonce_b64'], enc['tag_b64'])
        self.assertEqual(len(dec['minutiae']), len(TEMPLATE_VOTER_1['minutiae']))

    def test_sourceafis_genuine_match(self):
        """Test SourceAFIS matching accepts genuine probe with natural spatial jitter."""
        probe = generate_synthetic_fingerprint_template(seed_id=101, num_minutiae=38, noise_jitter=1.2)
        ref = TEMPLATE_VOTER_1  # Seed 101

        result = match_minutiae_templates(probe, ref)
        self.assertTrue(result['is_match'])
        self.assertGreaterEqual(result['similarity_score'], 40.0)
        self.assertIn(result['confidence'], ['HIGH', 'MEDIUM'])

    def test_sourceafis_impostor_rejection(self):
        """Test SourceAFIS matching rejects different/impostor fingerprint template."""
        probe = TEMPLATE_IMPOSTOR  # Seed 999
        ref = TEMPLATE_VOTER_1    # Seed 101

        result = match_minutiae_templates(probe, ref)
        self.assertFalse(result['is_match'])
        self.assertLess(result['similarity_score'], 40.0)
        self.assertEqual(result['confidence'], 'REJECTED')

    def test_far_frr_evaluation(self):
        """Test FAR/FRR benchmarking matrix produces valid metrics."""
        genuine = [75.0, 82.0, 68.0, 90.0, 55.0]
        impostor = [12.0, 18.0, 8.0, 22.0, 15.0]
        matrix = evaluate_far_frr(genuine, impostor, thresholds=[20.0, 40.0, 60.0])

        self.assertEqual(len(matrix), 3)
        # At T = 40.0, impostor max was 22.0 so FAR should be 0.0%
        row_40 = next(r for r in matrix if r['threshold'] == 40.0)
        self.assertEqual(row_40['FAR_percent'], 0.0)
        self.assertEqual(row_40['FRR_percent'], 0.0)
