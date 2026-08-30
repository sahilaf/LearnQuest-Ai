"""SQLAlchemy models.

Import every model module here so Alembic autogenerate can see them.
Add your import when you create your models file - one line, no reordering.
"""

from app.database import Base  # noqa: F401

# from app.models import user, course        # M3
# from app.models import progress, quiz      # M2
# from app.models import ai                  # M1
# from app.models import gamification        # M4
