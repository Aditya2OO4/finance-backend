"""
app/routes/users.py
-------------------
User management endpoints. All require users:read or users:write permission.
Only the admin role has these permissions.

  GET    /api/users              users:read   List all users (paginated)
  GET    /api/users/:id          users:read   Get single user
  PUT    /api/users/:id          users:write  Update name / role / status
  DELETE /api/users/:id          users:write  Hard-delete user
  PATCH  /api/users/:id/status   users:write  Toggle active ↔ inactive
"""

from app.models import user as user_model
from app.utils.helpers import (
    ok, error, not_found,
    parse_pagination, paginate_response,
)
from app.middleware.auth import require_permission


@require_permission("users:read")
def list_users(request):
    """List all users with pagination. Admin only."""
    page, limit, offset = parse_pagination(request.query_params)
    users, total = user_model.get_all(page, limit, offset)
    return ok(paginate_response(
        [user_model.safe_user(u) for u in users],
        total, page, limit,
    ))


@require_permission("users:read")
def get_user(request, user_id):
    """Get a single user by ID. Admin only."""
    user = user_model.find_by_id(user_id)
    if not user:
        return not_found("User")
    return ok(user_model.safe_user(user))


@require_permission("users:write")
def update_user(request, user_id):
    """Update a user's name, role, or status. Admin only."""
    if user_id == request.current_user["id"]:
        return error("You cannot modify your own account via this endpoint.", 400)

    if not user_model.find_by_id(user_id):
        return not_found("User")

    body = request.json or {}
    errs = []
    fields = {}

    if "name" in body:
        name = (body["name"] or "").strip()
        if not name:
            errs.append("name cannot be empty")
        else:
            fields["name"] = name

    if "role" in body:
        role = (body["role"] or "").strip().lower()
        if role not in user_model.VALID_ROLES:
            errs.append(f"role must be one of: {', '.join(sorted(user_model.VALID_ROLES))}")
        else:
            fields["role"] = role

    if "status" in body:
        status = (body["status"] or "").strip().lower()
        if status not in user_model.VALID_STATUSES:
            errs.append(f"status must be one of: {', '.join(sorted(user_model.VALID_STATUSES))}")
        else:
            fields["status"] = status

    if errs:
        return error("Validation failed", 422, errs)

    updated = user_model.update(user_id, fields)
    return ok(user_model.safe_user(updated))


@require_permission("users:write")
def delete_user(request, user_id):
    """Hard-delete a user. Admin only. Cannot delete yourself."""
    if user_id == request.current_user["id"]:
        return error("You cannot delete your own account.", 400)
    if not user_model.find_by_id(user_id):
        return not_found("User")
    user_model.delete(user_id)
    return ok({"message": "User deleted successfully"})


@require_permission("users:write")
def toggle_status(request, user_id):
    """Toggle a user's status between active and inactive. Admin only."""
    if user_id == request.current_user["id"]:
        return error("You cannot change your own status.", 400)

    user = user_model.find_by_id(user_id)
    if not user:
        return not_found("User")

    new_status = "inactive" if user["status"] == "active" else "active"
    updated = user_model.update(user_id, {"status": new_status})
    return ok(user_model.safe_user(updated))
