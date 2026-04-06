"""
seed.py
-------
Populates the database with demo users and financial records.
Run with:  python seed.py

Creates:
  admin@finance.dev   / Admin1234!   (role: admin)
  analyst@finance.dev / Analyst123!  (role: analyst)
  viewer@finance.dev  / Viewer123!   (role: viewer)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db
from app.models import user as user_model, record as record_model
from app.utils.auth import hash_password
import random
from datetime import date, timedelta

SEED_USERS = [
    {"name": "Alice Admin",   "email": "admin@finance.dev",   "password": "Admin1234!",   "role": "admin"},
    {"name": "Ana Analyst",   "email": "analyst@finance.dev", "password": "Analyst123!",  "role": "analyst"},
    {"name": "Victor Viewer", "email": "viewer@finance.dev",  "password": "Viewer123!",   "role": "viewer"},
]

CATEGORIES = {
    "income":  ["Salary", "Freelance", "Dividends", "Rental Income", "Bonus"],
    "expense": ["Rent", "Groceries", "Utilities", "Transport", "Healthcare",
                "Entertainment", "Software", "Marketing", "Insurance"],
}


def random_date(start_days_ago=365):
    delta = random.randint(0, start_days_ago)
    return (date.today() - timedelta(days=delta)).isoformat()


def seed():
    init_db()
    print("Seeding database...\n")

    created_users = []
    for u in SEED_USERS:
        existing = user_model.find_by_email(u["email"])
        if existing:
            print(f"  ⚠  User already exists: {u['email']}")
            created_users.append(existing)
        else:
            hashed = hash_password(u["password"])
            user   = user_model.create(u["name"], u["email"], hashed, u["role"])
            created_users.append(user)
            print(f"  ✓  Created user: {u['email']} ({u['role']})")

    print()

    # Create 80 random financial records for the admin user
    admin = next(u for u in created_users if u["role"] == "admin")
    count = 0
    for _ in range(80):
        type_    = random.choice(["income", "expense"])
        category = random.choice(CATEGORIES[type_])
        amount   = round(random.uniform(50, 5000), 2)
        rec = record_model.create(
            user_id  = admin["id"],
            amount   = amount,
            type_    = type_,
            category = category,
            date     = random_date(),
            notes    = f"Auto-generated {type_} entry",
        )
        count += 1

    print(f"  ✓  Created {count} financial records\n")

    print("="*50)
    print("Seed complete. Test credentials:\n")
    for u in SEED_USERS:
        print(f"  {u['role'].upper():8}  {u['email']}  /  {u['password']}")
    print("="*50)


if __name__ == "__main__":
    seed()
