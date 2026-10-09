"""Import every app's models so SQLAlchemy metadata (and Alembic autogenerate) sees them.

Add new apps here, like INSTALLED_APPS in Django.
"""

from apps.notifications.models import Device, Notification  # noqa: F401
from apps.users.models import SocialAccount, User  # noqa: F401
from kuulis.core.models import Base

metadata = Base.metadata
