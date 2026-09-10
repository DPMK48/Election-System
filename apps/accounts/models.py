import pyotp
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_ADMIN = 'admin'
    ROLE_ELECTORAL_OFFICER = 'electoral_officer'
    ROLE_CANDIDATE = 'candidate'
    ROLE_VOTER = 'voter'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'System Administrator'),
        (ROLE_ELECTORAL_OFFICER, 'Electoral Officer'),
        (ROLE_CANDIDATE, 'Candidate'),
        (ROLE_VOTER, 'Voter'),
    ]

    matric_no = models.CharField(max_length=50, unique=True, db_index=True, verbose_name='Matriculation / Staff ID')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_VOTER)
    faculty = models.CharField(max_length=150, blank=True, null=True)
    department = models.CharField(max_length=150, blank=True, null=True)
    level = models.IntegerField(default=100, help_text="Academic Level (e.g. 100, 200, 300, 400, 500)")
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    
    # MFA & Security fields
    is_verified = models.BooleanField(default=True, help_text="Verified in official university registry")
    totp_secret = models.CharField(max_length=64, blank=True, null=True)
    totp_enabled = models.BooleanField(default=False)
    biometric_enrolled = models.BooleanField(default=False)
    failed_login_attempts = models.IntegerField(default=0)
    is_locked = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'matric_no'
    REQUIRED_FIELDS = ['username', 'email']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['matric_no']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.matric_no}) - {self.get_role_display()}"

    def ensure_totp_secret(self):
        """Generate and save a TOTP secret if not present."""
        if not self.totp_secret:
            self.totp_secret = pyotp.random_base32()
            self.save(update_fields=['totp_secret'])
        return self.totp_secret

    def get_totp_uri(self, issuer_name="Apex University Election"):
        """Generate standard otpauth URI for QR code generation."""
        secret = self.ensure_totp_secret()
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=self.matric_no,
            issuer_name=issuer_name
        )

    def verify_totp(self, token, valid_window=1):
        """Verify an entered 6-digit OTP code."""
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(str(token).strip(), valid_window=valid_window)

    def is_admin_or_officer(self):
        return self.role in [self.ROLE_ADMIN, self.ROLE_ELECTORAL_OFFICER] or self.is_superuser
