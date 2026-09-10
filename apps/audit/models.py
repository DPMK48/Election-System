import hashlib
import json
from django.db import models
from django.utils import timezone

class AuditLog(models.Model):
    EVENT_SYSTEM_INIT = 'SYSTEM_INIT'
    EVENT_LOGIN_STEP1_SUCCESS = 'LOGIN_STEP1_SUCCESS'
    EVENT_LOGIN_STEP1_FAIL = 'LOGIN_STEP1_FAIL'
    EVENT_LOGIN_STEP2_SUCCESS = 'LOGIN_STEP2_SUCCESS'
    EVENT_LOGIN_STEP2_FAIL = 'LOGIN_STEP2_FAIL'
    EVENT_BIOMETRIC_MATCH_SUCCESS = 'BIOMETRIC_MATCH_SUCCESS'
    EVENT_BIOMETRIC_MATCH_FAIL = 'BIOMETRIC_MATCH_FAIL'
    EVENT_BIOMETRIC_ENROLL = 'BIOMETRIC_ENROLL'
    EVENT_BALLOT_CAST = 'BALLOT_CAST'
    EVENT_DOUBLE_VOTE_BLOCKED = 'DOUBLE_VOTE_BLOCKED'
    EVENT_STAGE_SKIP_BLOCKED = 'STAGE_SKIP_BLOCKED'
    EVENT_ADMIN_ACTION = 'ADMIN_ACTION'
    EVENT_SECURITY_LOCKOUT = 'SECURITY_LOCKOUT'
    EVENT_WEBAUTHN_REGISTER = 'WEBAUTHN_REGISTER'
    EVENT_WEBAUTHN_AUTH_SUCCESS = 'WEBAUTHN_AUTH_SUCCESS'
    EVENT_WEBAUTHN_AUTH_FAIL = 'WEBAUTHN_AUTH_FAIL'

    EVENT_CHOICES = [
        (EVENT_SYSTEM_INIT, 'System Initialized / Genesis Block'),
        (EVENT_LOGIN_STEP1_SUCCESS, 'Step 1: Password Authenticated'),
        (EVENT_LOGIN_STEP1_FAIL, 'Step 1: Password Failed'),
        (EVENT_LOGIN_STEP2_SUCCESS, 'Step 2: OTP Authenticated'),
        (EVENT_LOGIN_STEP2_FAIL, 'Step 2: OTP Failed'),
        (EVENT_BIOMETRIC_MATCH_SUCCESS, 'Step 3: Biometric Verified'),
        (EVENT_BIOMETRIC_MATCH_FAIL, 'Step 3: Biometric Rejected'),
        (EVENT_BIOMETRIC_ENROLL, 'Biometric Template Enrolled'),
        (EVENT_BALLOT_CAST, 'Ballot Cast & Cryptographically Sealed'),
        (EVENT_DOUBLE_VOTE_BLOCKED, 'Double-Vote Attempt Blocked'),
        (EVENT_STAGE_SKIP_BLOCKED, 'Authentication Stage-Skipping Blocked'),
        (EVENT_ADMIN_ACTION, 'Electoral Commission Administrative Action'),
        (EVENT_SECURITY_LOCKOUT, 'Account Locked (Exceeded Retries)'),
        (EVENT_WEBAUTHN_REGISTER, 'WebAuthn Device Fingerprint Enrolled'),
        (EVENT_WEBAUTHN_AUTH_SUCCESS, 'Step 3: Device Fingerprint Verified'),
        (EVENT_WEBAUTHN_AUTH_FAIL, 'Step 3: Device Fingerprint Rejected'),
    ]

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    event_type = models.CharField(max_length=50, choices=EVENT_CHOICES, db_index=True)
    user_id = models.IntegerField(blank=True, null=True)
    matric_no = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    ip_address = models.CharField(max_length=45, default='127.0.0.1')
    details = models.TextField(blank=True, help_text="JSON payload of event details")
    prev_hash = models.CharField(max_length=64, db_index=True)
    current_hash = models.CharField(max_length=64, unique=True, db_index=True)

    class Meta:
        verbose_name = 'Audit Log Entry'
        verbose_name_plural = 'Audit Log Entries (Hash-Chained)'
        ordering = ['id']

    def __str__(self):
        return f"Block #{self.id} | [{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.event_type} - {self.matric_no or 'ANONYMOUS'}"

    def compute_hash(self, prev_hash=None):
        """
        Compute SHA-256 hash chaining:
        H_n = SHA-256(prev_hash + timestamp_iso + event_type + user_id + matric_no + ip + details)
        """
        p_hash = prev_hash if prev_hash is not None else self.prev_hash
        ts_str = self.timestamp.isoformat() if self.timestamp else timezone.now().isoformat()
        payload = f"{p_hash}|{ts_str}|{self.event_type}|{self.user_id or ''}|{self.matric_no or ''}|{self.ip_address}|{self.details}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def is_tampered(self):
        """Check if this entry's current_hash matches recalculated hash."""
        recalculated = self.compute_hash()
        return recalculated != self.current_hash
