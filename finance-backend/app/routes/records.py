"""
app/routes/records.py
---------------------
Financial record CRUD endpoints.

Permission matrix:
  GET    /api/records         records:read    viewer, analyst, admin
  POST   /api/records         records:write   admin only
  GET    /api/records/:id     records:read    viewer, analyst, admin
  PUT    /api/records/:id     records:write   admin only
  DELETE /api/records/:id     records:write   admin only (soft delete)
"""

from app.models import record as record_model
from app.utils.helpers import (
    ok, created, error, not_found,
    validate_date, validate_amount,
    parse_pagination, paginate_response,
)
from app.middleware.auth import require_permission


@require_permission("records:read")
def list_records(request):
    """List all active records with optional filters and pagination."""
    page, limit, offset = parse_pagination(request.query_params)
    qp = request.query_params
    filters = {}
    errs = []

    if qp.get("type"):
        t = qp["type"].strip().lower()
        if t not in record_model.VALID_TYPES:
            errs.append(f"type must be one of: {', '.join(sorted(record_model.VALID_TYPES))}")
        else:
            filters["type"] = t

    if qp.get("category"):
        filters["category"] = qp["category"].strip()

    if qp.get("date_from"):
        if not validate_date(qp["date_from"]):
            errs.append("date_from must be YYYY-MM-DD")
        else:
            filters["date_from"] = qp["date_from"]

    if qp.get("date_to"):
        if not validate_date(qp["date_to"]):
            errs.append("date_to must be YYYY-MM-DD")
        else:
            filters["date_to"] = qp["date_to"]

    if errs:
        return error("Invalid filter parameters", 422, errs)

    if filters.get("date_from") and filters.get("date_to"):
        if filters["date_from"] > filters["date_to"]:
            return error("date_from cannot be after date_to", 422)

    records, total = record_model.get_all(filters, page, limit, offset)
    return ok(paginate_response(records, total, page, limit))


@require_permission("records:write")
def create_record(request):
    """Create a new financial record. Admin only."""
    body = request.json or {}
    errs = []

    amount   = body.get("amount")
    type_    = (body.get("type") or "").strip().lower()
    category = (body.get("category") or "").strip()
    date     = (body.get("date") or "").strip()
    notes    = (body.get("notes") or "").strip() or None

    if not validate_amount(amount):
        errs.append("amount must be a positive number")
    if type_ not in record_model.VALID_TYPES:
        errs.append(f"type must be one of: {', '.join(sorted(record_model.VALID_TYPES))}")
    if not category:
        errs.append("category is required")
    if not validate_date(date):
        errs.append("date must be in YYYY-MM-DD format")

    if errs:
        return error("Validation failed", 422, errs)

    rec = record_model.create(
        user_id  = request.current_user["id"],
        amount   = float(amount),
        type_    = type_,
        category = category,
        date     = date,
        notes    = notes,
    )
    return created(rec)


@require_permission("records:read")
def get_record(request, record_id):
    """Get a single record by ID."""
    rec = record_model.find_by_id(record_id)
    if not rec:
        return not_found("Record")
    return ok(rec)


@require_permission("records:write")
def update_record(request, record_id):
    """Partially update a record. Admin only."""
    rec = record_model.find_by_id(record_id)
    if not rec:
        return not_found("Record")

    body   = request.json or {}
    errs   = []
    fields = {}

    if "amount" in body:
        if not validate_amount(body["amount"]):
            errs.append("amount must be a positive number")
        else:
            fields["amount"] = float(body["amount"])

    if "type" in body:
        t = (body["type"] or "").strip().lower()
        if t not in record_model.VALID_TYPES:
            errs.append(f"type must be one of: {', '.join(sorted(record_model.VALID_TYPES))}")
        else:
            fields["type"] = t

    if "category" in body:
        cat = (body["category"] or "").strip()
        if not cat:
            errs.append("category cannot be empty")
        else:
            fields["category"] = cat

    if "date" in body:
        if not validate_date(body["date"]):
            errs.append("date must be in YYYY-MM-DD format")
        else:
            fields["date"] = body["date"]

    if "notes" in body:
        fields["notes"] = (body["notes"] or "").strip() or None

    if errs:
        return error("Validation failed", 422, errs)

    updated = record_model.update(record_id, fields)
    return ok(updated)


@require_permission("records:write")
def delete_record(request, record_id):
    """Soft-delete a record. Admin only. The row is retained for audit purposes."""
    rec = record_model.find_by_id(record_id)
    if not rec:
        return not_found("Record")
    record_model.soft_delete(record_id)
    return ok({"message": "Record deleted successfully"})
