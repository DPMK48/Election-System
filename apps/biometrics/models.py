from django.db import models
from django.conf import settings
from .crypto import encrypt_template, decrypt_template

class FingerprintTemplate(models.Model):
    FINGER_RIGHT_THUMB = 'RIGHT_THUMB'
    FINGER_RIGHT_INDEX = 'RIGHT_INDEX'
    FINGER_LEFT_THUMB = 'LEFT_THUMB'
    FINGER_LEFT_INDEX = 'LEFT_INDEX'

    FINGER_CHOICES = [
        (FINGER_RIGHT_THUMB, 'Right Thumb'),
        (FINGER_RIGHT_INDEX, 'Right Index Finger'),
        (FINGER_LEFT_THUMB, 'Left Thumb'),
        (FINGER_LEFT_INDEX, 'Left Index Finger'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fingerprint_template'
    )
    finger_index = models.CharField(max_length=30, choices=FINGER_CHOICES, default=FINGER_RIGHT_INDEX)
    
    # AES-256 GCM encrypted fields at rest
    encrypted_template = models.TextField(help_text="AES-256 GCM ciphertext of minutiae features (Base64)")
    nonce = models.CharField(max_length=64, help_text="GCM 96-bit nonce (Base64)")
    tag = models.CharField(max_length=64, help_text="GCM 128-bit authentication tag (Base64)")
    
    minutiae_count = models.IntegerField(default=0)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Fingerprint Template'
        verbose_name_plural = 'Fingerprint Templates (Encrypted at Rest)'

    def __str__(self):
        return f"Fingerprint Template for {self.user.matric_no} ({self.get_finger_index_display()}) - {self.minutiae_count} minutiae"

    def set_template_data(self, template_dict):
        """Encrypts and sets the minutiae template data."""
        encrypted_pkg = encrypt_template(template_dict)
        self.encrypted_template = encrypted_pkg['ciphertext_b64']
        self.nonce = encrypted_pkg['nonce_b64']
        self.tag = encrypted_pkg['tag_b64']
        minutiae_list = template_dict.get('minutiae', [])
        self.minutiae_count = len(minutiae_list)

    def get_template_data(self):
        """Decrypts and returns the minutiae template dictionary in memory."""
        return decrypt_template(self.encrypted_template, self.nonce, self.tag)


class WebAuthnCredential(models.Model):
    """
    Stores a FIDO2 / WebAuthn credential registered from a student's personal device.
    The device's built-in biometric sensor (fingerprint, face) handles identity verification
    locally on-device. Only the public key is stored server-side — the private key and
    biometric data never leave the device.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='webauthn_credentials'
    )
    credential_id = models.TextField(
        unique=True,
        help_text="Base64URL-encoded credential ID from the authenticator"
    )
    public_key = models.TextField(
        help_text="Base64URL-encoded COSE public key bytes"
    )
    sign_count = models.PositiveIntegerField(
        default=0,
        help_text="Signature counter for replay attack detection"
    )
    device_name = models.CharField(
        max_length=200,
        default='Personal Device',
        help_text="Friendly name for the enrolled device (e.g. Samsung Galaxy, iPhone)"
    )
    registered_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'WebAuthn Credential'
        verbose_name_plural = 'WebAuthn Credentials (FIDO2 Device Keys)'

    def __str__(self):
        return f"WebAuthn [{self.device_name}] for {self.user.matric_no} (registered {self.registered_at})"

