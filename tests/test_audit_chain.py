from django.test import TestCase
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.ledger import ensure_genesis_block, log_audit_event, verify_audit_chain, GENESIS_HASH

class AuditChainTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="20/54321U/1",
            matric_no="20/54321U/1",
            password="VoterPass123!"
        )


    def test_genesis_block_initialization(self):
        """Test Genesis block is created at Block #1 with 64 zeroes as prev_hash."""
        genesis = ensure_genesis_block()
        self.assertEqual(genesis.id, 1)
        self.assertEqual(genesis.prev_hash, GENESIS_HASH)
        self.assertEqual(genesis.current_hash, genesis.compute_hash(GENESIS_HASH))

    def test_hash_chain_sequential_integrity(self):
        """Test that appending multiple audit blocks creates an unbroken SHA-256 chain."""
        b1 = log_audit_event(AuditLog.EVENT_LOGIN_STEP1_SUCCESS, user=self.user)
        b2 = log_audit_event(AuditLog.EVENT_LOGIN_STEP2_SUCCESS, user=self.user)
        b3 = log_audit_event(AuditLog.EVENT_BIOMETRIC_MATCH_SUCCESS, user=self.user)

        self.assertEqual(b2.prev_hash, b1.current_hash)
        self.assertEqual(b3.prev_hash, b2.current_hash)

        # Full chain validation
        health = verify_audit_chain()
        self.assertTrue(health['is_valid'])
        self.assertIsNone(health['tampered_block_id'])

    def test_tamper_detection(self):
        """Test that modifying a historical audit block is flagged by the chain verifier."""
        b1 = log_audit_event(AuditLog.EVENT_LOGIN_STEP1_SUCCESS, user=self.user)
        b2 = log_audit_event(AuditLog.EVENT_BALLOT_CAST, user=self.user, details={"election": "SUG"})
        b3 = log_audit_event(AuditLog.EVENT_ADMIN_ACTION, user=self.user)

        # Malicious attacker attempts to silently edit Block 2 payload in DB without updating hashes
        AuditLog.objects.filter(id=b2.id).update(details='{"election": "TAMPERED_PAYLOAD"}')

        health = verify_audit_chain()
        self.assertFalse(health['is_valid'])
        self.assertEqual(health['tampered_block_id'], b2.id)
        self.assertIn("Tampered content", health['error_message'])
