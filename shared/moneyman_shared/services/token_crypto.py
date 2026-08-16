from cryptography.fernet import Fernet

from moneyman_shared.config import get_settings

# Phase 1 stand-in: symmetric Fernet encryption keyed by a single env-var secret
# (TOKEN_ENCRYPTION_KEY). The architecture plan specifies Cloud KMS envelope
# encryption for production (per-tenant/per-record data encryption keys wrapped
# by a KMS-managed key, with rotation and audit logging) — this module is the
# seam to swap that in later without touching callers.


def _fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
