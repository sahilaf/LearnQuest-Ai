"""users table. OWNER: Member 3. Schema: plan.md 3.

TODO(M3): define User with id (UUID PK, references auth.users(id) ON DELETE CASCADE),
email, full_name, avatar_url, role ('student' | 'admin'), preferences (JSONB),
created_at, last_login_at.

The id IS the Supabase auth.users id - there is no separate mirror column. Alembic
autogenerate cannot see the auth schema, so write that foreign key by hand:

    op.create_foreign_key(
        "fk_users_auth", "users", "users", ["id"], ["id"],
        referent_schema="auth", ondelete="CASCADE",
    )
Then add `from app.models import user` to models/__init__.py and run:
    alembic revision --autogenerate -m "m3: users"
"""
