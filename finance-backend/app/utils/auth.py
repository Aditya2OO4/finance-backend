"""
app/utils/auth.py
-----------------
Password hashing (PBKDF2-SHA256 via hashlib) and JWT-like token
handling (HMAC-SHA256 signed, base64url encoded).

We avoid third-party libs intentionally to keep the project
dependency-free; the approach is production-grade for an
assessment — in production you'd use bcrypt + python-jose.
"""

import hashlib
import hmac
import base64
import json
import os
import time
import uuid

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
TOKEN_TTL  = int(os.environ.get("TOKEN_TTL_SECONDS", 3600))   # 1 hour default


# ─────────────────────────────────────────────────────────────
# Password helpers
# ─────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return a salted PBKDF2-SHA256 hash in  salt$hash  format."""
    salt = uuid.uuid4().hex
    hashed = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 260_000)
    return f"{salt}${hashed.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    """Constant-time comparison of a plain password against stored hash."""
    try:
        salt, stored_hash = stored.split("$", 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 260_000)
    return hmac.compare_digest(candidate.hex(), stored_hash)


# ─────────────────────────────────────────────────────────────
# JWT helpers  (Header.Payload.Signature — all base64url)
# ─────────────────────────────────────────────────────────────

def _b64_encode(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def _b64_decode(s: str) -> dict:
    # Re-add padding
    padded = s + "=" * (-len(s) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def create_token(user_id: str, role: str) -> str:
    header  = _b64_encode({"alg": "HS256", "typ": "JWT"})
    payload = _b64_encode({
        "sub":  user_id,
        "role": role,
        "iat":  int(time.time()),
        "exp":  int(time.time()) + TOKEN_TTL,
    })
    signature = hmac.new(
        SECRET_KEY.encode(),
        f"{header}.{payload}".encode(),
        hashlib.sha256,
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{header}.{payload}.{sig_b64}"


def decode_token(token: str) -> dict:
    """
    Decode and verify a token.
    Returns payload dict on success.
    Raises ValueError with a descriptive message on failure.
    """
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError:
        raise ValueError("Malformed token")

    expected_sig = hmac.new(
        SECRET_KEY.encode(),
        f"{header_b64}.{payload_b64}".encode(),
        hashlib.sha256,
    ).digest()
    expected_b64 = base64.urlsafe_b64encode(expected_sig).rstrip(b"=").decode()

    if not hmac.compare_digest(expected_b64, sig_b64):
        raise ValueError("Invalid token signature")

    payload = _b64_decode(payload_b64)

    if payload.get("exp", 0) < time.time():
        raise ValueError("Token has expired")

    return payload
