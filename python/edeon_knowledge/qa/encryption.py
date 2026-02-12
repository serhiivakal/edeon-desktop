import base64
import uuid
import hashlib
from cryptography.fernet import Fernet

def get_machine_key() -> bytes:
    """Derives a stable 32-byte key from the host hardware MAC address."""
    # uuid.getnode() returns the 48-bit integer representing the MAC address
    node = uuid.getnode()
    h = hashlib.sha256(str(node).encode('utf-8')).digest()
    # Convert to URL-safe base64 key format required by Fernet
    return base64.urlsafe_b64encode(h)

def encrypt_value(plain_text: str) -> str:
    """Encrypts a string value at rest using machine key Fernet cipher."""
    if not plain_text:
        return ""
    key = get_machine_key()
    f = Fernet(key)
    return f.encrypt(plain_text.encode('utf-8')).decode('utf-8')

def decrypt_value(cipher_text: str) -> str:
    """Decrypts a machine-key cipher-text value back to a plain string."""
    if not cipher_text:
        return ""
    try:
        key = get_machine_key()
        f = Fernet(key)
        return f.decrypt(cipher_text.encode('utf-8')).decode('utf-8')
    except Exception as e:
        # If decryption fails (e.g. key mismatch or plain value was passed in error), return empty
        raise ValueError(f"Failed to decrypt settings value: {e}")
