"""Convert raw API payloads into result models."""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from .const import MEDICATION_MOMENT_TITLES
from .models import (
    AccountMembership,
    BasketItem,
    ConversationSummary,
    CustomerBasket,
    DraftBasket,
    FarmadAccount,
    FarmadMessage,
    FarmadPatient,
    MedicationDayScheme,
    MedicationIntakeMoment,
    MedicationNondailyProduct,
    MedicationSchemeProduct,
    MedicationTemporality,
    PatientInPharmacy,
    Pharmacy,
    PharmacyPreferences,
    Prescription,
)

_TEMPORALITY_ORDER: dict[MedicationTemporality, int] = {
    temporality: index
    for index, temporality in enumerate(
        (
            MedicationTemporality.ACUTE,
            MedicationTemporality.CHRONIC,
            MedicationTemporality.AD_HOC,
            MedicationTemporality.OTHER,
            MedicationTemporality.UNKNOWN,
        )
    )
}


def _str_field(data: Mapping[str, Any], key: str, default: str = "") -> str:
    value = data.get(key)
    return value if isinstance(value, str) else default


def _int_field(data: Mapping[str, Any], key: str) -> int | None:
    value = data.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _bool_field(data: Mapping[str, Any], key: str) -> bool:
    return data.get(key) is True


def _datetime_field(data: Mapping[str, Any], key: str) -> datetime | None:
    value = data.get(key)
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_account(data: Mapping[str, Any]) -> FarmadAccount:
    """Build the account model from the account payload."""
    memberships = tuple(
        AccountMembership(
            user_id=_str_field(item, "userId"),
            group_id=_str_field(item, "groupId"),
            group_name=_str_field(item, "groupName"),
            group_description=_str_field(item, "groupDescription"),
            group_owner=_str_field(item, "groupOwner"),
            from_=_datetime_field(item, "from"),
        )
        for item in _mapping_items(data.get("memberships"))
    )
    return FarmadAccount(
        id=_str_field(data, "id"),
        email=_str_field(data, "email"),
        first_name=_str_field(data, "firstName"),
        last_name=_str_field(data, "lastName"),
        full_name=_str_field(data, "fullName"),
        language=_str_field(data, "language"),
        blocked=_bool_field(data, "blocked"),
        logins_count=_int_field(data, "loginsCount") or 0,
        memberships=memberships,
        raw=dict(data),
    )


def parse_patient(data: Mapping[str, Any]) -> FarmadPatient:
    """Build the patient model from the patient payload."""
    per_apb = data.get("patient_in_apbs")
    pharmacies: list[PatientInPharmacy] = []
    if isinstance(per_apb, Mapping):
        for item in per_apb.values():
            if not isinstance(item, Mapping):
                continue
            pharmacies.append(
                PatientInPharmacy(
                    apb_number=_str_field(item, "apbNumber"),
                    customer_number=_int_field(item, "customerNumber"),
                    patient_id=_str_field(item, "patientId"),
                    name=_str_field(item, "name"),
                    first_name=_str_field(item, "firstName"),
                    gender=_str_field(item, "gender"),
                    date_of_birth=_datetime_field(item, "dateOfBirth"),
                    communication_language_code=_str_field(item, "communicationLanguageCode"),
                    last_visit=_datetime_field(item, "lastVisit"),
                )
            )
    return FarmadPatient(
        patient_id=_str_field(data, "patientId"),
        pharmacies=tuple(sorted(pharmacies, key=lambda p: p.apb_number)),
    )


def parse_organization(data: Mapping[str, Any]) -> Pharmacy:
    """Build the pharmacy model from the organization payload."""
    return Pharmacy(
        apb=_str_field(data, "apb"),
        name=_str_field(data, "name"),
        city=_str_field(data, "city"),
        email=_str_field(data, "email") or None,
        raw=dict(data),
    )


def parse_pharmacy_preferences(data: Mapping[str, Any]) -> PharmacyPreferences:
    """Build the order preferences from the pharmacy preferences payload."""
    return PharmacyPreferences(
        allow_online_payments=_bool_field(data, "allowOnlinePayments"),
        can_receive_payment_at_delivery_hatch=_bool_field(data, "canReceivePaymentAtDeliveryHatch"),
        allow_automatic_export=_bool_field(data, "allowAutomaticExport"),
        is_lochting_pharmacy=_bool_field(data, "isLochtingPharmacy"),
    )


def parse_day_scheme(data: Mapping[str, Any]) -> MedicationDayScheme:
    """Build one day scheme from a single day payload."""
    moments: list[MedicationSchemeProduct] = []
    skipped = 0
    for row in _mapping_items(data.get("moments")):
        order = _int_field(row, "order")
        if order is None or order not in MEDICATION_MOMENT_TITLES:
            skipped += 1
            continue
        moments.append(
            MedicationSchemeProduct(
                product_description=_str_field(row, "productDescription").lower(),
                description=_str_field(row, "description"),
                cnk=_str_field(row, "cnk"),
                temporality=_temporality(row.get("temporality")),
                order=order,
            )
        )
    grouped: dict[str, MedicationIntakeMoment] = {}
    for product in moments:
        title = MEDICATION_MOMENT_TITLES[product.order]
        moment = grouped.get(title)
        if moment is None:
            grouped[title] = MedicationIntakeMoment(
                title=title,
                order=product.order,
                products=(product,),
            )
        else:
            merged = sorted(
                (*moment.products, product),
                key=lambda p: (_TEMPORALITY_ORDER[p.temporality], p.product_description),
            )
            grouped[title] = MedicationIntakeMoment(
                title=title,
                order=min(moment.order, product.order),
                products=tuple(merged),
            )
    ordered = sorted(grouped.values(), key=_moment_sort_key)
    return MedicationDayScheme(
        date=_parse_day(data.get("day")),
        intake_moments=tuple(ordered),
        skipped_moments=skipped,
    )


def parse_day_scheme_range(data: Any) -> tuple[MedicationDayScheme, ...]:
    """Build every day scheme from the day scheme range payload."""
    if not isinstance(data, list):
        return ()
    return tuple(parse_day_scheme(item) for item in data if isinstance(item, Mapping))


def parse_nondaily_products(data: Any) -> tuple[MedicationNondailyProduct, ...]:
    """Group the nondaily medication payload by product."""
    if not isinstance(data, list):
        return ()
    products: dict[str, MedicationNondailyProduct] = {}
    skipped_dosages = 0
    for item in data:
        if not isinstance(item, Mapping):
            skipped_dosages += 1
            continue
        cnk = _str_field(item, "cnk")
        dosage = _str_field(item, "dosage").strip()
        existing = products.get(cnk)
        if existing is None:
            products[cnk] = MedicationNondailyProduct(
                cnk=cnk,
                product_description=_str_field(item, "productDescription").lower(),
                dosages=(dosage,) if dosage else (),
                skipped_dosages=0 if dosage else 1,
            )
            continue
        if not dosage:
            products[cnk] = MedicationNondailyProduct(
                cnk=existing.cnk,
                product_description=existing.product_description,
                dosages=existing.dosages,
                skipped_dosages=existing.skipped_dosages + 1,
            )
        elif dosage in existing.dosages:
            products[cnk] = MedicationNondailyProduct(
                cnk=existing.cnk,
                product_description=existing.product_description,
                dosages=existing.dosages,
                skipped_dosages=existing.skipped_dosages,
            )
        else:
            products[cnk] = MedicationNondailyProduct(
                cnk=existing.cnk,
                product_description=existing.product_description,
                dosages=(*existing.dosages, dosage),
                skipped_dosages=existing.skipped_dosages,
            )
    return tuple(products.values())


def parse_message(data: Mapping[str, Any]) -> FarmadMessage:
    """Build a message model from the message payload."""
    sender = data.get("sender")
    sender_id = ""
    sender_name = ""
    if isinstance(sender, Mapping):
        sender_id = _str_field(sender, "id")
        sender_name = _str_field(sender, "displayName")
    return FarmadMessage(
        id=_str_field(data, "id"),
        reference=_str_field(data, "reference"),
        body=_str_field(data, "body"),
        sent=_datetime_field(data, "send"),
        sender_id=sender_id,
        sender_name=sender_name,
        read_by_receiver=_bool_field(data, "readByReceiver"),
        raw=dict(data),
    )


def parse_conversation(data: Mapping[str, Any]) -> ConversationSummary:
    """Build a conversation model from the conversation summary payload."""
    last_message = data.get("lastMessage")
    return ConversationSummary(
        customer_id=_str_field(data, "customerId"),
        customer_name=_str_field(data, "customerName"),
        last_message=parse_message(last_message) if isinstance(last_message, Mapping) else None,
        unread_message_count=_int_field(data, "unreadMessageCount") or 0,
        raw=dict(data),
    )


def parse_conversations(data: Any) -> tuple[ConversationSummary, ...]:
    """Build every conversation from the conversation list payload."""
    if not isinstance(data, list):
        return ()
    return tuple(parse_conversation(item) for item in data if isinstance(item, Mapping))


def parse_baskets(data: Mapping[str, Any]) -> tuple[CustomerBasket, ...]:
    """Build baskets from the basket list payload, resolving patient names."""
    embedded: dict[str, str] = {}
    for patient in _mapping_items(data.get("embeddedPatients")):
        embedded_patient_id = _str_field(patient, "id")
        first = _str_field(patient, "firstName")
        last = _str_field(patient, "name")
        embedded[embedded_patient_id] = " ".join(part for part in (first, last) if part).strip()
    baskets: list[CustomerBasket] = []
    for item in _mapping_items(data.get("results")):
        patient_id: str | None = _str_field(item, "customerPatientId") or None
        notification_info = item.get("notificationInfo")
        fallback_name = ""
        if isinstance(notification_info, Mapping):
            fallback_name = _str_field(notification_info, "customEmailAddress")
        baskets.append(
            CustomerBasket(
                id=_str_field(item, "id"),
                customer_patient_id=patient_id,
                customer_patient_name=embedded.get(patient_id or "") or fallback_name or None,
                state=_str_field(item, "state"),
                items=parse_basket_items(item.get("basketItems")),
                raw=dict(item),
            )
        )
    return tuple(baskets)


def parse_basket_items(data: Any) -> tuple[BasketItem, ...]:
    """Build basket lines from the basket items payload."""
    if not isinstance(data, list):
        return ()
    items: list[BasketItem] = []
    for item in data:
        if not isinstance(item, Mapping):
            continue
        unit_price = item.get("unitPrice")
        items.append(
            BasketItem(
                product_cnk=_str_field(item, "productCnk"),
                quantity=_int_field(item, "quantity") or 0,
                unit_price=unit_price if isinstance(unit_price, int | float) else None,
            )
        )
    return tuple(items)


def parse_draft_basket(data: Mapping[str, Any]) -> DraftBasket:
    """Build the draft basket model from the draft payload."""
    return DraftBasket(
        id=_str_field(data, "id") or None,
        comment=_str_field(data, "comment") or None,
        items=parse_basket_items(data.get("basketItems")),
        raw=dict(data),
    )


def parse_prescription(payload: Any, prescription_id: str = "") -> Prescription | None:
    """Build one prescription from its payload, keeping the shape in raw."""
    if payload is None:
        return None
    if isinstance(payload, dict):
        return Prescription(prescription_id=prescription_id, raw=payload)
    return Prescription(prescription_id=prescription_id)


def parse_prescriptions(payload: Any) -> tuple[Prescription, ...]:
    """Build every prescription from the list payload, whatever shape it takes."""
    if isinstance(payload, list):
        return tuple(Prescription(raw=dict(item)) for item in payload if isinstance(item, dict))
    if isinstance(payload, dict):
        for key in ("items", "hits", "results", "prescriptions"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return tuple(
                    Prescription(raw=dict(item)) for item in nested if isinstance(item, dict)
                )
        return (Prescription(raw=dict(payload)),)
    return ()


def _mapping_items(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _temporality(value: Any) -> MedicationTemporality:
    if isinstance(value, str):
        for temporality in MedicationTemporality:
            if temporality.value == value:
                return temporality
    return MedicationTemporality.UNKNOWN


def _moment_sort_key(moment: MedicationIntakeMoment) -> tuple[int, int]:
    if moment.title == MEDICATION_MOMENT_TITLES[998]:
        return (0, moment.order)
    return (1, moment.order)


def _parse_day(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None
