"""
Crypto-Tracer: DPDP Act 2023 Compliant PII Encryption Module.
Implements AES-256-GCM authenticated encryption at rest with HKDF-SHA256 key derivation
and SQLAlchemy TypeDecorator transparent field converters.
"""
import os
import base64
import binascii
from functools import lru_cache
from typing import Optional, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag
from sqlalchemy.types import TypeDecorator, Text

from backend.app.config import settings

# Cryptographic Constants
HKDF_SALT = b"crypto-tracer-dpdp-pii-salt-2026"
HKDF_INFO = b"crypto-tracer-aes-256-gcm-pii-at-rest"
NONCE_LENGTH_BYTES = 12
TAG_LENGTH_BYTES = 16
MIN_PAYLOAD_BYTES = NONCE_LENGTH_BYTES + TAG_LENGTH_BYTES  # 28 bytes


class CryptoError(Exception):
    """Base exception for cryptographic operations."""
    pass


class DecryptionError(CryptoError):
    """Raised when ciphertext payload is corrupted or authentication tag fails."""
    pass


@lru_cache(maxsize=4)
def get_encryption_key(key_override: Optional[str] = None) -> bytes:
    """
    Derives a 256-bit (32-byte) AES key from settings.encryption_key_value (or explicit override).
    Uses HKDF-SHA256 (RFC 5869) for cryptographically robust key expansion.
    """
    if key_override:
        raw_key = key_override.strip()
    else:
        raw_key = settings.encryption_key_value.strip()

    if not raw_key:
        raise CryptoError("Cannot derive encryption key: SECRET_KEY and ENCRYPTION_KEY are empty.")

    # Direct 64-char hex key support
    if len(raw_key) == 64:
        try:
            return bytes.fromhex(raw_key)
        except ValueError:
            pass

    # HKDF-SHA256 derivation
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=HKDF_SALT,
        info=HKDF_INFO,
    )
    return hkdf.derive(raw_key.encode("utf-8"))


def encrypt_text(
    plaintext: Optional[str],
    associated_data: Optional[bytes] = None,
    key_override: Optional[str] = None,
) -> Optional[str]:
    """
    Encrypts plaintext using AES-256-GCM with a fresh CSPRNG 12-byte nonce.
    Returns: base64(nonce + ciphertext + tag)
    """
    if plaintext is None:
        return None
    if not isinstance(plaintext, str):
        plaintext = str(plaintext)

    key = get_encryption_key(key_override)
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_LENGTH_BYTES)
    data_bytes = plaintext.encode("utf-8")

    ciphertext_and_tag = aesgcm.encrypt(nonce, data_bytes, associated_data)
    combined = nonce + ciphertext_and_tag
    return base64.b64encode(combined).decode("ascii")


def decrypt_text(
    ciphertext_b64: Optional[str],
    associated_data: Optional[bytes] = None,
    key_override: Optional[str] = None,
) -> Optional[str]:
    """
    Decrypts base64(nonce + ciphertext + tag) using AES-256-GCM.
    Gracefully returns original value if legacy unencrypted plaintext is encountered.
    """
    if ciphertext_b64 is None:
        return None
    if not isinstance(ciphertext_b64, str):
        return str(ciphertext_b64)
    if not ciphertext_b64.strip():
        return ciphertext_b64

    # Check for valid base64
    try:
        combined = base64.b64decode(ciphertext_b64.encode("ascii"), validate=True)
    except (binascii.Error, ValueError):
        # Not base64: legacy plaintext row
        return ciphertext_b64

    # Must contain at least nonce (12B) + tag (16B) = 28B
    if len(combined) < MIN_PAYLOAD_BYTES:
        return ciphertext_b64

    nonce = combined[:NONCE_LENGTH_BYTES]
    ciphertext_and_tag = combined[NONCE_LENGTH_BYTES:]

    try:
        key = get_encryption_key(key_override)
        aesgcm = AESGCM(key)
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext_and_tag, associated_data)
        return decrypted_bytes.decode("utf-8")
    except (InvalidTag, UnicodeDecodeError):
        # Graceful fallback for legacy plaintext rows
        return ciphertext_b64


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy TypeDecorator for transparent field-level AES-256-GCM encryption.
    Stores data as Base64 encoded Text in database while presenting str in Python.
    """
    impl = Text
    cache_ok = True

    def __init__(self, length: Optional[int] = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.length = length

    def process_bind_param(self, value: Optional[str], dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return encrypt_text(value)

    def process_result_value(self, value: Optional[str], dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return decrypt_text(value)


class EncryptedText(EncryptedString):
    """Alias for large encrypted text fields (notes, narratives)."""
    impl = Text
    cache_ok = True
