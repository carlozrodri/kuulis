"""Import every app's models so SQLAlchemy metadata (and Alembic autogenerate) sees them.

Add new apps here, like INSTALLED_APPS in Django.
"""

from apps.approvals.models import PendingApproval  # noqa: F401
from apps.audit.models import AuditLog  # noqa: F401
from apps.auth.models import UserTotp  # noqa: F401
from apps.config.models import AppSetting  # noqa: F401
from apps.control.models import Announcement, FeatureFlag  # noqa: F401
from apps.drivers.models import DriverDocument, DriverProfile, Vehicle  # noqa: F401
from apps.legal.models import LegalAcceptance, LegalDocument  # noqa: F401
from apps.moderation.models import Report, ReportMessage, ReportNote, Suspension  # noqa: F401
from apps.notifications.models import Device, Notification  # noqa: F401
from apps.places.models import SavedPlace  # noqa: F401
from apps.privacy.models import DataExport, ErasedEmail, UserConsent  # noqa: F401
from apps.promotions.models import Promotion  # noqa: F401
from apps.rates.models import ExchangeRate  # noqa: F401
from apps.referrals.models import Referral  # noqa: F401
from apps.releases.models import AppRelease  # noqa: F401
from apps.rides.models import (  # noqa: F401
    Rating,
    Ride,
    RideCancellation,
    RideMessage,
    RideOffer,
)
from apps.safety.models import (  # noqa: F401
    RideShareLink,
    RideTrack,
    SafetyAlert,
    TrustedContact,
)
from apps.quality.models import QualityPause, QualityStats  # noqa: F401
from apps.staff.models import StaffRole  # noqa: F401
from apps.subscriptions.models import Charge, FeeSchedule  # noqa: F401
from apps.support.models import CannedResponse, HelpArticle, LostItemRequest  # noqa: F401
from apps.updates.models import AppUpdate  # noqa: F401
from apps.users.models import SocialAccount, User  # noqa: F401
from apps.wallet.models import TopUp, Wallet, WalletEntry  # noqa: F401
from kuulis.core.models import Base

metadata = Base.metadata
