"""users table. OWNER: Member 3. Schema: plan.md 3.

TODO(M3): define User with firebase_uid (unique), email, full_name, avatar_url,
role ('student' | 'admin'), preferences (JSONB), created_at, last_login_at.
Then add `from app.models import user` to models/__init__.py and run:
    alembic revision --autogenerate -m "m3: users"
"""
