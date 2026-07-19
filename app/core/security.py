
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import REPO_ROOT, settings

_KEY_FILE = REPO_ROOT / ".secret.key"


def _load_or_create_key() -> bytes:
    if settings.secret_key:
        digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    return key


_fernet = Fernet(_load_or_create_key())


def encrypt_secret(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Could not decrypt secret (wrong key?)") from exc


def mask_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    if len(plaintext) <= 8:
        return "•" * len(plaintext)
    return f"{plaintext[:3]}…{plaintext[-4:]}"
