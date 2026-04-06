# Finance Backend API

A clean, well-structured finance dashboard backend built entirely on **Python standard library** — no third-party frameworks or packages required. Uses SQLite for persistence, HMAC-SHA256-signed JWTs for stateless authentication, and a custom HTTP router inspired by Flask/Express patterns.

---

## Tech Stack

| Layer          | Technology                                      |
|----------------|-------------------------------------------------|
| Language       | Python 3.10+                                    |
| HTTP Server    | `http.server` (stdlib)                          |
| Database       | SQLite 3 via `sqlite3` (stdlib)                 |
| Auth           | Custom JWT — HMAC-SHA256, base64url encoded     |
| Password Hash  | PBKDF2-SHA256, 260k iterations (stdlib hashlib) |
| Rate Limiting  | In-memory sliding window per IP                 |
| Tests          | `unittest` + `http.client` (stdlib)             |
| Dependencies   | **Zero** — pure Python stdlib only              |

---

## Project Structure

```
finance-backend/
├── main.py                   # Entry point — starts the HTTP server
├── seed.py                   # Populates DB with demo users and records
├── requirements.txt          # Documents stdlib modules used (no installs needed)
│
├── app/
│   ├── database.py           # SQLite schema + db() context manager
│   │
│   ├── models/               # Data layer — pure SQL functions, return plain dicts
│   │   ├── user.py           # User CRUD
│   │   ├── record.py         # Financial record CRUD + soft delete
│   │   └── dashboard.py      # Aggregation queries (summary, trends, categories)
│   │
│   ├── routes/               # Request handlers — parse input, call models, return response
│   │   ├── auth.py           # Register, login, /me
│   │   ├── users.py          # User management (admin only)
│   │   ├── records.py        # Financial record CRUD
│   │   └── dashboard.py      # Analytics endpoints
│   │
│   ├── middleware/
│   │   ├── auth.py           # JWT verification, RBAC decorators, permission registry
│   │   └── rate_limit.py     # Sliding-window rate limiter
│   │
│   └── utils/
│       ├── auth.py           # Password hashing + JWT sign/verify
│       └── helpers.py        # Response builders, validators, pagination
│
└── tests/
    └── test_api.py           # 58 integration tests (spins up real server + in-memory DB)
```

---

## Setup & Running

### Requirements
- Python 3.10 or higher
- No pip installs needed

### Start the server

```bash
python main.py
```

Server starts at `http://localhost:8000`.

### Seed demo data

```bash
python seed.py
```

Creates 3 users (admin / analyst / viewer) and 80 random financial records.

### Run tests

```bash
python -m unittest tests/test_api.py -v
```

All 58 tests run against an isolated in-memory SQLite database.

### Environment Variables

| Variable             | Default          | Description                              |
|----------------------|------------------|------------------------------------------|
| `PORT`               | `8000`           | HTTP port                                |
| `HOST`               | `0.0.0.0`        | Bind address                             |
| `DB_PATH`            | `finance.db`     | SQLite file (use `:memory:` for tests)   |
| `SECRET_KEY`         | `dev-secret-...` | JWT signing secret — **change in prod**  |
| `TOKEN_TTL_SECONDS`  | `3600`           | JWT lifetime (seconds)                   |
| `RATE_LIMIT_WINDOW`  | `60`             | Rate limit window (seconds)              |
| `RATE_LIMIT_MAX`     | `100`            | Max requests per window per IP           |
| `RATE_LIMIT_DISABLE` | `0`              | Set to `1` to disable (used in tests)    |

---

## Roles & Permissions

### Role Definitions

| Role        | Description                                              |
|-------------|----------------------------------------------------------|
| **viewer**  | Read-only access to records and basic dashboard data     |
| **analyst** | Viewer access + trend analytics (monthly/weekly charts)  |
| **admin**   | Full access: CRUD on records, user management, all data  |

### Permission Matrix

| Permission            | Viewer | Analyst | Admin |
|-----------------------|:------:|:-------:|:-----:|
| `records:read`        | ✓      | ✓       | ✓     |
| `records:write`       |        |         | ✓     |
| `dashboard:summary`   | ✓      | ✓       | ✓     |
| `dashboard:categories`| ✓      | ✓       | ✓     |
| `dashboard:activity`  | ✓      | ✓       | ✓     |
| `dashboard:trends`    |        | ✓       | ✓     |
| `users:read`          |        |         | ✓     |
| `users:write`         |        |         | ✓     |

Permissions are defined in a single registry in `app/middleware/auth.py` (`ROLE_PERMISSIONS`). Every route is decorated with `@require_permission("permission:name")` — the system never relies on ad-hoc role string checks scattered across handlers.

---

## API Reference

### Response Envelope

All responses use a consistent structure:

```json
{ "success": true,  "data": { ... } }
{ "success": false, "error": "Human-readable message", "details": ["..."] }
```

### Authentication

| Method | Endpoint              | Auth | Description                      |
|--------|-----------------------|------|----------------------------------|
| `POST` | `/api/auth/register`  | —    | Create a new account             |
| `POST` | `/api/auth/login`     | —    | Authenticate and receive a token |
| `GET`  | `/api/auth/me`        | Any  | Get current user info            |

**Register body:**
```json
{
  "name": "Alice Admin",
  "email": "alice@example.com",
  "password": "SecurePass1!",
  "role": "admin"
}
```
> Roles: `viewer` | `analyst` | `admin`

**Login response:**
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGci...",
    "user": { "id": "uuid", "name": "Alice Admin", "email": "...", "role": "admin" }
  }
}
```

**Token usage:** Include in every subsequent request:
```
Authorization: Bearer <token>
```

---

### Financial Records

| Method   | Endpoint               | Permission      | Description                    |
|----------|------------------------|-----------------|--------------------------------|
| `GET`    | `/api/records`         | `records:read`  | List records (paginated)       |
| `POST`   | `/api/records`         | `records:write` | Create a record (admin)        |
| `GET`    | `/api/records/:id`     | `records:read`  | Get a single record            |
| `PUT`    | `/api/records/:id`     | `records:write` | Update a record (admin)        |
| `DELETE` | `/api/records/:id`     | `records:write` | Soft-delete a record (admin)   |

**Create / Update body:**
```json
{
  "amount": 2500.00,
  "type": "income",
  "category": "Salary",
  "date": "2024-04-01",
  "notes": "April salary"
}
```
> `type` must be `income` or `expense`. `amount` must be a positive number. `date` must be `YYYY-MM-DD`.

**Query filters (GET /api/records):**
```
?type=income
?category=Salary
?date_from=2024-01-01
?date_to=2024-12-31
?page=1&limit=20
```

---

### Dashboard Analytics

| Method | Endpoint                        | Permission              | Description                      |
|--------|---------------------------------|-------------------------|----------------------------------|
| `GET`  | `/api/dashboard/summary`        | `dashboard:summary`     | Income, expenses, net balance    |
| `GET`  | `/api/dashboard/categories`     | `dashboard:categories`  | Totals grouped by category       |
| `GET`  | `/api/dashboard/trends/monthly` | `dashboard:trends`      | Monthly trends (analyst + admin) |
| `GET`  | `/api/dashboard/trends/weekly`  | `dashboard:trends`      | Weekly trends (analyst + admin)  |
| `GET`  | `/api/dashboard/activity`       | `dashboard:activity`    | Recent transactions feed         |

**Data scoping:**
- Admins see data for all users (optionally filtered by `?user_id=`)
- Viewers and analysts see only their own data

**Summary response:**
```json
{
  "total_income": 15000.00,
  "total_expenses": 8200.50,
  "net_balance": 6799.50,
  "total_records": 42
}
```

**Monthly trends response:**
```json
[
  { "month": "2024-02", "income": 5000.00, "expenses": 2800.00, "net": 2200.00 },
  { "month": "2024-03", "income": 5000.00, "expenses": 2900.00, "net": 2100.00 }
]
```
> Optional param: `?months=6` (default 12, max 60)

---

### User Management (Admin only)

| Method    | Endpoint                   | Permission    | Description                  |
|-----------|----------------------------|---------------|------------------------------|
| `GET`     | `/api/users`               | `users:read`  | List all users (paginated)   |
| `GET`     | `/api/users/:id`           | `users:read`  | Get user by ID               |
| `PUT`     | `/api/users/:id`           | `users:write` | Update name / role / status  |
| `DELETE`  | `/api/users/:id`           | `users:write` | Hard-delete a user           |
| `PATCH`   | `/api/users/:id/status`    | `users:write` | Toggle active ↔ inactive     |

> Admins cannot modify or delete their own account through these endpoints.

---

### Health Check

```
GET /health
→ { "status": "ok", "service": "finance-backend" }
```

---

## Example API Flow

```bash
# 1. Register an admin account
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice","email":"alice@example.com","password":"Secret123!","role":"admin"}'

# 2. Login to get a token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"Secret123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])")

# 3. Create a financial record
curl -X POST http://localhost:8000/api/records \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount":3000,"type":"income","category":"Salary","date":"2024-04-01"}'

# 4. Get dashboard summary
curl http://localhost:8000/api/dashboard/summary \
  -H "Authorization: Bearer $TOKEN"

# 5. Filter records by type and date
curl "http://localhost:8000/api/records?type=income&date_from=2024-01-01&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# 6. Access monthly trends (analyst or admin only)
curl http://localhost:8000/api/dashboard/trends/monthly?months=6 \
  -H "Authorization: Bearer $TOKEN"
```

---

## Seed Credentials

After running `python seed.py`:

| Role      | Email                   | Password      |
|-----------|-------------------------|---------------|
| `admin`   | admin@finance.dev       | `Admin1234!`  |
| `analyst` | analyst@finance.dev     | `Analyst123!` |
| `viewer`  | viewer@finance.dev      | `Viewer123!`  |

80 randomised financial records are created for the admin account.

---

## Design Decisions & Assumptions

### Zero External Dependencies
All functionality is built on Python stdlib (`http.server`, `sqlite3`, `hashlib`, `hmac`, `uuid`, `re`, `threading`). This makes the project instantly runnable on any Python 3.10+ environment with no install step. In a production project you'd use FastAPI + bcrypt + python-jose + SQLAlchemy, but the patterns here are identical.

### JWT Implementation
Hand-rolled HMAC-SHA256 signed tokens in standard `header.payload.signature` format. Signature verification uses `hmac.compare_digest` for constant-time comparison (prevents timing attacks). In production: use `python-jose` or `PyJWT`.

### Password Hashing
PBKDF2-SHA256 with 260,000 iterations and a random UUID4 salt per password. Stored as `salt$hash`. Verification is constant-time. In production: use `bcrypt`.

### Permission-Based RBAC
Rather than role strings scattered across handlers, all permissions live in a single `ROLE_PERMISSIONS` registry in `app/middleware/auth.py`. Every route is decorated with `@require_permission("resource:action")`. This means changing what an analyst can do requires editing exactly one dict, not hunting through routes.

### Soft Delete for Records
Financial records set `deleted_at` instead of being hard-deleted. This preserves the audit trail. All queries filter `WHERE deleted_at IS NULL`. Hard delete is only available for users (admin endpoint).

### Data Scoping by Role
Dashboard endpoints scope data to the current user for viewers and analysts. Admins see all records. This is enforced at the SQL `WHERE` clause level, not application code, so it cannot be accidentally bypassed.

### SQLite with WAL Mode
WAL (Write-Ahead Logging) allows concurrent reads without blocking writes — appropriate for a single-node SQLite deployment. For multi-instance: use PostgreSQL with SQLAlchemy.

### Rate Limiting
In-memory sliding window: 100 requests per 60 seconds per IP. Thread-safe via `threading.Lock`. For distributed deployments: back with Redis.

### In-Memory DB for Tests
Tests set `DB_PATH=:memory:` and reuse a single connection (SQLite in-memory databases are per-connection; a singleton avoids schema loss between calls). Rate limiting is disabled in tests via `RATE_LIMIT_DISABLE=1`.

---

## Optional Features Implemented

- **JWT authentication** with expiry and signature verification
- **Pagination** on all list endpoints (`page`, `limit`, `total_pages`)
- **Soft delete** on financial records (audit-safe)
- **Seed script** with realistic randomised data
- **Rate limiting** (100 req/min per IP, configurable)
- **CORS headers** for local frontend development
- **Health check** endpoint
- **58 integration tests** covering auth, RBAC, CRUD, validation, and edge cases
