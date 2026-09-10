import base64
import json
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from django.conf import settings

# AES-256 Key is configured in Django settings
AES_KEY = getattr(settings, 'AES_FINGERPRINT_KEY', b'apex_univ_biometric_aes_key_32b!')

def encrypt_template(template_dict):
    """
    Encrypts a fingerprint minutiae template dictionary using AES-256 GCM.
    Returns:
        dict: {
            'ciphertext_b64': str,
            'nonce_b64': str,
            'tag_b64': str
        }
    """
    json_bytes = json.dumps(template_dict).encode('utf-8')
    nonce = get_random_bytes(12)  # 96-bit nonce for GCM
    cipher = AES.new(AES_KEY, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(json_bytes)

    return {
        'ciphertext_b64': base64.b64encode(ciphertext).decode('utf-8'),
        'nonce_b64': base64.b64encode(nonce).decode('utf-8'),
        'tag_b64': base64.b64encode(tag).decode('utf-8')
    }

def decrypt_template(ciphertext_b64, nonce_b64, tag_b64):
    """
    Decrypts an AES-256 GCM encrypted fingerprint template.
    Returns:
        dict: The decrypted template dictionary containing minutiae points.
    Raises:
        ValueError: If ciphertext or authentication tag is invalid.
    """
    ciphertext = base64.b64decode(ciphertext_b64)
    nonce = base64.b64decode(nonce_b64)
    tag = base64.b64decode(tag_b64)

    cipher = AES.new(AES_KEY, AES.MODE_GCM, nonce=nonce)
    decrypted_bytes = cipher.decrypt_and_verify(ciphertext, tag)
    return json.loads(decrypted_bytes.decode('utf-8'))
