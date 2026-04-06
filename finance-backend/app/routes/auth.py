"""
app/routes/auth.py
------------------
POST /api/auth/register   – create a new account
POST /api/auth/login      – get a JWT token
GET  /api/auth/me         – get current user info
"""

from app.models import user as user_model
from app.utils.auth import hash_password, verify_password, create_token
from app.utils.helpers import ok, created, error, unauthorized, validate_email
from app.middleware.auth import require_auth


def register(request):
    body = request.json or {}

    # ── Validation ───────────────────────────────────────────
    errs = []
    name     = (body.get("name") or "").strip()
    email    = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    role     = (body.get("role") or "viewer").strip().lower()

    if not name:
        errs.append("name is required")
    if not validate_email(email):
        errs.append("valid email is required")
    if len(password) < 8:
        errs.append("password must be at least 8 characters")
    if role not in user_model.VALID_ROLES:
        errs.append(f"role must be one of: {', '.join(user_model.VALID_ROLES)}")

    if errs:
        return error("Validation failed", 422, errs)

    # ── Uniqueness check ─────────────────────────────────────
    if user_model.find_by_email(email):
        return error("An account with this email already exists", 409)

    # ── Create ───────────────────────────────────────────────
    hashed = hash_password(password)
    user   = user_model.create(name, email, hashed, role)
    token  = create_token(user["id"], user["role"])

    return created({
        "user":  user_model.safe_user(user),
        "token": token,
    })


def login(request):
    body = request.json or {}

    email    = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        return error("email and password are required", 422)

    user = user_model.find_by_email(email)
    if not user or not verify_password(password, user["password"]):
        return unauthorized("Invalid email or password")

    if user["status"] != "active":
        return error("Your account has been deactivated", 403)

    token = create_token(user["id"], user["role"])
    return ok({
        "user":  user_model.safe_user(user),
        "token": token,
    })


@require_auth
def me(request):
    return ok(user_model.safe_user(request.current_user))
