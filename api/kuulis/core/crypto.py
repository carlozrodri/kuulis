"""Symmetric encryption for small secrets stored in the database (TOTP seeds).

The key derives from SECRET_KEY: rotating SECRET_KEY makes the stored secrets unreadable, so the
team re-enrolls their authenticators after a rotation (docs/deployment.md).
"""

import base64
import hashlib
from functools import cache

from cryptography.fernet import Fernet

from kuulis.settings import settings


@cache
def _fernet() -> Fernet:
    digest = hashlib.sha256(b"kuulis:secrets:" + settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
