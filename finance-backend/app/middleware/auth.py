"""
app/middleware/auth.py
----------------------
Authentication and Role-Based Access Control (RBAC).

Three layers:
  1. get_current_user()    – validates JWT, loads user from DB
  2. @require_auth         – any valid, active user
  3. @require_permission() – enforces a named permission from ROLE_PERMISSIONS

Role permission matrix (single source of truth):
  viewer   → read records + basic dashboard
  analyst  → viewer + trend analytics
  admin    → full access including user management and record mutation
"""

import functools
from app.utils.auth import decode_token
from app.utils.helpers import unauthorized, forbidden
from app.models import user as user_model


# ─────────────────────────────────────────────────────────────
# Permission registry  (single source of truth for all RBAC)
# ─────────────────────────────────────────────────────────────

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {
        "records:read",
        "dashboard:summary",
        "dashboard:categories",
        "dashboard:activity",
    },
    "analyst": {
        "records:read",
        "dashboard:summary",
        "dashboard:categories",
        "dashboard:activity",
        "dashboard:trends",       # monthly + weekly trends
    },
    "admin": {
        "records:read",
        "records:write",          # create + update + delete
        "dashboard:summary",
        "dashboard:categories",
        "dashboard:activity",
        "dashboard:trends",
        "users:read",
        "users:write",            # create / update / delete / toggle status
    },
}


def has_permission(user: dict, permission: str) -> bool:
    """Check whether a user's role grants the given permission."""
    return permission in ROLE_PERMISSIONS.get(user.get("role", ""), set())


# ─────────────────────────────────────────────────────────────
# Token + user resolution
# ─────────────────────────────────────────────────────────────

def get_current_user(headers: dict) -> dict:
    """
    Extract and verify the Bearer token from Authorization header.
    Returns the user dict on success, raises ValueError on failure.
    """
    auth_header = headers.get("Authorization", "") or headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing or malformed Authorization header")

    token = auth_header[len("Bearer "):]
    payload = decode_token(token)       # raises ValueError if invalid/expired

    user = user_model.find_by_id(payload["sub"])
    if not user:
        raise ValueError("User not found")
    if user["status"] != "active":
        raise ValueError("Account is inactive. Contact an administrator.")

    return user


# ─────────────────────────────────────────────────────────────
# Decorator: any authenticated user
# ─────────────────────────────────────────────────────────────

def require_auth(handler):
    """Ensures the request carries a valid JWT. Attaches user to request."""
    @functools.wraps(handler)
    def wrapper(request, *args, **kwargs):
        try:
            user = get_current_user(request.headers)
        except ValueError as e:
            return unauthorized(str(e))
        request.current_user = user
        return handler(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────
# Decorator: permission-gated access
# ─────────────────────────────────────────────────────────────

def require_permission(permission: str):
    """
    Decorator factory. Validates JWT then checks ROLE_PERMISSIONS.

    Usage:
        @require_permission("records:write")
        @require_permission("users:read")

    Returns 401 if unauthenticated, 403 if authenticated but lacking permission.
    """
    def decorator(handler):
        @functools.wraps(handler)
        def wrapper(request, *args, **kwargs):
            try:
                user = get_current_user(request.headers)
            except ValueError as e:
                return unauthorized(str(e))

            if not has_permission(user, permission):
                role = user.get("role", "unknown")
                return forbidden(
                    f"Your role '{role}' does not have '{permission}' permission."
                )

            request.current_user = user
            return handler(request, *args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────
# Legacy helper — kept for any direct role checks in route logic
# ─────────────────────────────────────────────────────────────

def require_role(*allowed_roles):
    """
    Restrict to explicit role names. Prefer require_permission() for new code.
    Kept for admin-only user management routes where role semantics are clearer.
    """
    def decorator(handler):
        @functools.wraps(handler)
        def wrapper(request, *args, **kwargs):
            try:
                user = get_current_user(request.headers)
            except ValueError as e:
                return unauthorized(str(e))
            if user["role"] not in allowed_roles:
                return forbidden(
                    f"This action requires one of these roles: {', '.join(allowed_roles)}"
                )
            request.current_user = user
            return handler(request, *args, **kwargs)
        return wrapper
    return decorator
