from __future__ import annotations

import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from database.config.config import settings


VERSION = 'aesgcm-v1'
CHAT_AAD = b'loanhub-chat-message-v1'
FILE_AAD = b'loanhub-managed-file-v1'
CONTROL_VERSION = 'aesgcm-control-v1'


def _derive_key(raw_value: str, purpose: bytes) -> bytes:
    """Derive a stable 256-bit key without exposing the configured secret.

    Production deployments should provide separate CHAT_ENCRYPTION_KEY and
    FILE_ENCRYPTION_KEY values. FERNET_SECRET_KEY is retained only as a
    backward-compatible source when those values are absent.
    """
    if not raw_value:
        raise RuntimeError('An encryption key is required')
    return hashlib.sha256(raw_value.encode('utf-8') + b':' + purpose).digest()


def _chat_key() -> bytes:
    return _derive_key(
        settings.CHAT_ENCRYPTION_KEY or settings.FERNET_SECRET_KEY,
        CHAT_AAD,
    )


def _file_key() -> bytes:
    return _derive_key(
        settings.FILE_ENCRYPTION_KEY or settings.FERNET_SECRET_KEY,
        FILE_AAD,
    )


def _control_key(purpose: bytes) -> bytes:
    return _derive_key(settings.FERNET_SECRET_KEY, purpose)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode('ascii')


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode('ascii'))


def encrypt_chat_text(value: str) -> tuple[str, str, str]:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_chat_key()).encrypt(
        nonce,
        value.encode('utf-8'),
        CHAT_AAD,
    )
    return _encode(ciphertext), _encode(nonce), VERSION


def decrypt_chat_text(
    ciphertext: str | None,
    nonce: str | None,
    version: str | None,
) -> str | None:
    if not ciphertext:
        return None
    if version != VERSION or not nonce:
        raise ValueError('Unsupported encrypted chat message format')
    try:
        plaintext = AESGCM(_chat_key()).decrypt(
            _decode(nonce),
            _decode(ciphertext),
            CHAT_AAD,
        )
    except (InvalidTag, ValueError) as error:
        raise ValueError('Encrypted chat message could not be verified') from error
    return plaintext.decode('utf-8')


def encrypt_file_bytes(content: bytes) -> tuple[bytes, str, str]:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_file_key()).encrypt(
        nonce,
        content,
        FILE_AAD,
    )
    return ciphertext, _encode(nonce), VERSION


def decrypt_file_bytes(
    content: bytes,
    nonce: str | None,
    version: str | None,
) -> bytes:
    if version != VERSION or not nonce:
        raise ValueError('Unsupported encrypted file format')
    try:
        return AESGCM(_file_key()).decrypt(
            _decode(nonce),
            content,
            FILE_AAD,
        )
    except (InvalidTag, ValueError) as error:
        raise ValueError('Encrypted file could not be verified') from error


def encrypt_control_secret(value: str, purpose: bytes) -> tuple[str, str, str]:
    """Encrypt an operational secret with purpose-bound authenticated encryption."""
    nonce = os.urandom(12)
    ciphertext = AESGCM(_control_key(purpose)).encrypt(
        nonce,
        value.encode('utf-8'),
        purpose,
    )
    return _encode(ciphertext), _encode(nonce), CONTROL_VERSION


def decrypt_control_secret(
    ciphertext: str,
    nonce: str,
    version: str,
    purpose: bytes,
) -> str:
    if version != CONTROL_VERSION:
        raise ValueError('Unsupported encrypted control-secret format')
    try:
        value = AESGCM(_control_key(purpose)).decrypt(
            _decode(nonce),
            _decode(ciphertext),
            purpose,
        )
    except (InvalidTag, ValueError) as error:
        raise ValueError('Encrypted control secret could not be verified') from error
    return value.decode('utf-8')
