from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from database.config.config import settings


VERSION = "credential-v1"
AAD = b"loanhub-payment-provider-credentials-v1"


def _key() -> bytes:
    raw = settings.FERNET_SECRET_KEY or settings.SECRET_KEY
    if not raw:
        raise RuntimeError("A platform encryption key is required for provider credentials")
    return hashlib.sha256(raw.encode("utf-8") + b":" + AAD).digest()


def encrypt_credential(value: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, value.encode("utf-8"), AAD)
    return ":".join(
        [
            VERSION,
            base64.urlsafe_b64encode(nonce).decode("ascii"),
            base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        ]
    )


def decrypt_credential(value: str) -> str:
    try:
        version, nonce_text, ciphertext_text = value.split(":", 2)
        if version != VERSION:
            raise ValueError("Unsupported credential encryption version")
        nonce = base64.urlsafe_b64decode(nonce_text.encode("ascii"))
        ciphertext = base64.urlsafe_b64decode(ciphertext_text.encode("ascii"))
        clear = AESGCM(_key()).decrypt(nonce, ciphertext, AAD)
        return clear.decode("utf-8")
    except Exception as error:
        raise RuntimeError("Stored provider credentials could not be decrypted") from error


def mask_secret(value: str | None, *, visible: int = 4) -> str:
    if not value:
        return ""
    clean = value.strip()
    if len(clean) <= visible:
        return "*" * len(clean)
    return f"{'*' * max(4, len(clean) - visible)}{clean[-visible:]}"
