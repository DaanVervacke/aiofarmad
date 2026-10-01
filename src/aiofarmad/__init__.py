"""Public API for aiofarmad."""

import importlib.metadata

from .client import FarmadClient, TokenRefreshCallback
from .exceptions import (
    FarmadAuthenticationError,
    FarmadAuthorizationError,
    FarmadClientClosedError,
    FarmadCommunicationError,
    FarmadEhealthAuthorizationRequiredError,
    FarmadError,
    FarmadInvalidResponseError,
    FarmadMfaRequiredError,
    FarmadNotFoundError,
    FarmadTimeoutError,
)
from .models import (
    AccountMembership,
    BasketItem,
    BasketLine,
    ConversationSummary,
    CustomerBasket,
    DraftBasket,
    DraftProduct,
    FarmadAccount,
    FarmadMessage,
    FarmadPatient,
    FarmadTokens,
    MedicationDayScheme,
    MedicationIntakeMoment,
    MedicationNondailyProduct,
    MedicationSchemeProduct,
    MedicationTemporality,
    PatientInPharmacy,
    Pharmacy,
    PharmacyLinkResult,
    PharmacyPreferences,
    Prescription,
)

try:
    __version__ = importlib.metadata.version("aiofarmad")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "AccountMembership",
    "BasketItem",
    "BasketLine",
    "ConversationSummary",
    "CustomerBasket",
    "DraftBasket",
    "DraftProduct",
    "FarmadAccount",
    "FarmadAuthenticationError",
    "FarmadAuthorizationError",
    "FarmadClient",
    "FarmadClientClosedError",
    "FarmadCommunicationError",
    "FarmadEhealthAuthorizationRequiredError",
    "FarmadError",
    "FarmadInvalidResponseError",
    "FarmadMessage",
    "FarmadMfaRequiredError",
    "FarmadNotFoundError",
    "FarmadPatient",
    "FarmadTimeoutError",
    "FarmadTokens",
    "MedicationDayScheme",
    "MedicationIntakeMoment",
    "MedicationNondailyProduct",
    "MedicationSchemeProduct",
    "MedicationTemporality",
    "PatientInPharmacy",
    "Pharmacy",
    "PharmacyLinkResult",
    "PharmacyPreferences",
    "Prescription",
    "TokenRefreshCallback",
    "__version__",
]
