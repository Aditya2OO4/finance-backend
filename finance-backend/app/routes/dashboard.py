"""
app/routes/dashboard.py
------------------------
Dashboard analytics endpoints.

Permission matrix:
  GET /api/dashboard/summary        dashboard:summary     viewer, analyst, admin
  GET /api/dashboard/categories     dashboard:categories  viewer, analyst, admin
  GET /api/dashboard/trends/monthly dashboard:trends      analyst, admin only
  GET /api/dashboard/trends/weekly  dashboard:trends      analyst, admin only
  GET /api/dashboard/activity       dashboard:activity    viewer, analyst, admin

Data scoping:
  - admin → all users' data (optionally filtered by ?user_id=)
  - viewer / analyst → their own data only
"""

from app.models import dashboard as dash_model
from app.utils.helpers import ok, error
from app.middleware.auth import require_permission


def _scoped_user_id(request) -> str | None:
    """
    Return None (= global) for admins so they see all data.
    Return the current user's ID for viewers and analysts.
    Admins can optionally scope to one user via ?user_id= query param.
    """
    if request.current_user["role"] == "admin":
        return request.query_params.get("user_id") or None
    return request.current_user["id"]


@require_permission("dashboard:summary")
def summary(request):
    """Total income, total expenses, net balance, and record count."""
    user_id = _scoped_user_id(request)
    return ok(dash_model.get_summary(user_id))


@require_permission("dashboard:categories")
def categories(request):
    """Totals grouped by category and type (income / expense)."""
    user_id = _scoped_user_id(request)
    return ok(dash_model.get_category_breakdown(user_id))


@require_permission("dashboard:trends")
def monthly_trends(request):
    """Income vs expense by calendar month. Analyst and Admin only."""
    user_id = _scoped_user_id(request)
    try:
        months = min(60, max(1, int(request.query_params.get("months", 12))))
    except (ValueError, TypeError):
        return error("months must be a positive integer", 422)
    return ok(dash_model.get_monthly_trends(user_id, months))


@require_permission("dashboard:trends")
def weekly_trends(request):
    """Income vs expense by ISO week. Analyst and Admin only."""
    user_id = _scoped_user_id(request)
    try:
        weeks = min(52, max(1, int(request.query_params.get("weeks", 8))))
    except (ValueError, TypeError):
        return error("weeks must be a positive integer", 422)
    return ok(dash_model.get_weekly_trends(user_id, weeks))


@require_permission("dashboard:activity")
def recent_activity(request):
    """Most recent N transactions for the activity feed."""
    user_id = _scoped_user_id(request)
    try:
        limit = min(50, max(1, int(request.query_params.get("limit", 10))))
    except (ValueError, TypeError):
        return error("limit must be a positive integer", 422)
    return ok(dash_model.get_recent_activity(user_id, limit))
