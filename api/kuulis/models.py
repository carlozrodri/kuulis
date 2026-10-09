"""Import every app's models so SQLAlchemy metadata (and Alembic autogenerate) sees them.

Add new apps here, like INSTALLED_APPS in Django.
"""

from apps.config.models import AppSetting  # noqa: F401
from apps.drivers.models import DriverDocument, DriverProfile, Vehicle  # noqa: F401
from apps.moderation.models import Report, ReportNote, Suspension  # noqa: F401
from apps.notifications.models import Device, Notification  # noqa: F401
from apps.promotions.models import Promotion  # noqa: F401
from apps.rates.models import ExchangeRate  # noqa: F401
from apps.rides.models import Rating, Ride, RideMessage, RideOffer  # noqa: F401
from apps.subscriptions.models import Charge, FeeSchedule  # noqa: F401
from apps.users.models import SocialAccount, User  # noqa: F401
from apps.wallet.models import TopUp, Wallet, WalletEntry  # noqa: F401
from kuulis.core.models import Base

metadata = Base.metadata
