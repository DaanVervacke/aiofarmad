"""Immutable result models for the Farmad Procura customer API."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class MedicationTemporality(StrEnum):
    """How long a medication is taken."""

    ACUTE = "acute"
    CHRONIC = "chronic"
    AD_HOC = "adHoc"
    OTHER = "other"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AccountMembership:
    """A pharmacy group the account belongs to."""

    user_id: str
    group_id: str
    group_name: str
    group_description: str
    group_owner: str
    from_: datetime | None = None


@dataclass(frozen=True, slots=True)
class FarmadAccount:
    """The logged-in customer account."""

    id: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    language: str
    blocked: bool
    logins_count: int
    memberships: tuple[AccountMembership, ...] = ()
    raw: dict[str, Any] | None = None

    @property
    def entitled_pharmacies(self) -> tuple[str, ...]:
        """The apb numbers of every pharmacy that granted this account a role."""
        return tuple(dict.fromkeys(m.group_owner for m in self.memberships if m.group_owner))


@dataclass(frozen=True, slots=True)
class PatientInPharmacy:
    """The patient record as one pharmacy knows it."""

    apb_number: str
    customer_number: int | None
    patient_id: str
    name: str
    first_name: str
    gender: str
    date_of_birth: datetime | None
    communication_language_code: str
    last_visit: datetime | None


@dataclass(frozen=True, slots=True)
class FarmadPatient:
    """The patient linked to the account, per pharmacy."""

    patient_id: str
    pharmacies: tuple[PatientInPharmacy, ...] = ()

    def pharmacy(self, apb_number: str) -> PatientInPharmacy | None:
        """Return the patient record at one pharmacy, or None when absent."""
        return next(
            (p for p in self.pharmacies if p.apb_number == apb_number),
            None,
        )


@dataclass(frozen=True, slots=True)
class Pharmacy:
    """Public pharmacy information."""

    apb: str
    name: str
    city: str
    email: str | None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class PharmacyPreferences:
    """What the pharmacy allows for online orders."""

    allow_online_payments: bool
    can_receive_payment_at_delivery_hatch: bool
    allow_automatic_export: bool
    is_lochting_pharmacy: bool


@dataclass(frozen=True, slots=True)
class MedicationSchemeProduct:
    """One medication inside an intake moment."""

    product_description: str
    description: str
    cnk: str
    temporality: MedicationTemporality
    order: int


@dataclass(frozen=True, slots=True)
class MedicationIntakeMoment:
    """A group of intakes that share a moment of the day."""

    title: str
    order: int
    products: tuple[MedicationSchemeProduct, ...] = ()


@dataclass(frozen=True, slots=True)
class MedicationDayScheme:
    """Every intake planned on one day."""

    date: date | None
    intake_moments: tuple[MedicationIntakeMoment, ...] = ()
    skipped_moments: int = 0

    @property
    def medication_count(self) -> int:
        """Total number of intakes across all moments of the day."""
        return sum(len(moment.products) for moment in self.intake_moments)


@dataclass(frozen=True, slots=True)
class MedicationNondailyProduct:
    """A medication taken outside the daily scheme, with its dosages."""

    cnk: str
    product_description: str
    dosages: tuple[str, ...] = ()
    skipped_dosages: int = 0


@dataclass(frozen=True, slots=True)
class FarmadMessage:
    """One message in a conversation with a pharmacy."""

    id: str
    reference: str
    body: str
    sent: datetime | None
    sender_id: str
    sender_name: str
    read_by_receiver: bool
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    """A conversation with one pharmacy."""

    customer_id: str
    customer_name: str
    last_message: FarmadMessage | None
    unread_message_count: int
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class BasketItem:
    """One product line inside a basket."""

    product_cnk: str
    quantity: int
    unit_price: float | None


@dataclass(frozen=True, slots=True)
class CustomerBasket:
    """A basket: a draft order or a submitted order."""

    id: str
    customer_patient_id: str | None
    customer_patient_name: str | None
    state: str
    items: tuple[BasketItem, ...] = ()
    raw: dict[str, Any] | None = None

    @property
    def total_price(self) -> float:
        """The basket total based on known unit prices."""
        return sum(
            item.quantity * item.unit_price for item in self.items if item.unit_price is not None
        )

    @property
    def item_count(self) -> int:
        """Total quantity across all basket lines."""
        return sum(item.quantity for item in self.items)


@dataclass(frozen=True, slots=True)
class DraftBasket:
    """The basket being built, before submission."""

    id: str | None
    comment: str | None
    items: tuple[BasketItem, ...] = ()
    raw: dict[str, Any] | None = None

    @property
    def item_count(self) -> int:
        """Total quantity across all draft lines."""
        return sum(item.quantity for item in self.items)


@dataclass(frozen=True, slots=True)
class FarmadTokens:
    """A token pair as issued by the Farmad login."""

    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    scope: str | None = None

    @classmethod
    def from_token_response(cls, tokens: dict[str, str]) -> FarmadTokens:
        """Build a token pair from the raw OAuth response fields."""
        return cls(
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_in=int(tokens["expires_in"]) if "expires_in" in tokens else None,
            scope=tokens.get("scope"),
        )


@dataclass(frozen=True, slots=True)
class Prescription:
    """One prescription as the eHealth service reports it.

    The payload shape stays in ``raw`` until a real consented session is
    captured, because the app bundle embeds no field map for it.
    """

    prescription_id: str = ""
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class PharmacyLinkResult:
    """The outcome of a pharmacy self-onboarding request."""

    apb: str
    accepted: bool
