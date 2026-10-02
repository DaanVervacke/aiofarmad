"""Convert raw API payloads into result models."""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from .const import MEDICATION_MOMENT_TITLES
from .models import (
    AccountMembership,
    BasketItem,
    BasketLine,
    BasketPayment,
    CatalogProduct,
    CatalogProductCode,
    CatalogProductPrice,
    CatalogProductStock,
    ConversationSummary,
    CustomerBasket,
    DraftBasket,
    FarmadAccount,
    FarmadMessage,
    FarmadPatient,
    KavaProduct,
    MedicationDayScheme,
    MedicationIntakeMoment,
    MedicationNondailyProduct,
    MedicationSchemeProduct,
    MedicationSchemeProductEntry,
    MedicationTemporality,
    MessageDraft,
    MessageDraftAttachment,
    MessageDraftAttachmentVariant,
    PatientInPharmacy,
    Pharmacy,
    PharmacyPreferences,
    Prescription,
    ServiceMessage,
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


def _float_field(data: Mapping[str, Any], key: str) -> float | None:
    value = data.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
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
    scheme_products: list[MedicationSchemeProduct] = []
    skipped = 0
    for row in _mapping_items(data.get("moments")):
        order = _int_field(row, "order")
        if order is None or order not in MEDICATION_MOMENT_TITLES:
            skipped += 1
            continue
        scheme_products.append(
            MedicationSchemeProduct(
                product_description=_str_field(row, "productDescription").lower(),
                description=_str_field(row, "description"),
                cnk=_str_field(row, "cnk"),
                temporality=_temporality(row.get("temporality")),
                order=order,
            )
        )
    grouped: dict[str, MedicationIntakeMoment] = {}
    for product in scheme_products:
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
    for item in data:
        if not isinstance(item, Mapping):
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


def _descriptions_field(value: Any) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(name): item for name, item in value.items() if isinstance(item, str)}


def _product_codes_field(value: Any) -> tuple[CatalogProductCode, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        CatalogProductCode(
            code_type=_str_field(item, "codeType"),
            code_value=_str_field(item, "codeValue"),
        )
        for item in value
        if isinstance(item, Mapping)
    )


def parse_catalog_product_price(data: Any) -> CatalogProductPrice | None:
    """Build the price model from the currentPriceInfo payload."""
    if not isinstance(data, Mapping):
        return None
    return CatalogProductPrice(
        sales_price=_float_field(data, "salesPrice"),
        promo_price_online=_float_field(data, "promoPriceOnline"),
        discount_percentage_online=_float_field(data, "discountPercentageOnline"),
        sales_tva_percentage=_float_field(data, "salesTvaPercentage"),
        base_price=_float_field(data, "basePrice"),
    )


def parse_catalog_product_stock(data: Any) -> CatalogProductStock | None:
    """Build the stock model from the currentStockInfo payload."""
    if not isinstance(data, Mapping):
        return None
    return CatalogProductStock(
        availability=_str_field(data, "availabilityCode"),
        total_in_stock=_int_field(data, "totalQuantityInStock"),
        quantity_in_robot=_int_field(data, "quantityInRobot"),
        has_robot_location=_bool_field(data, "hasRobotLocation"),
    )


def parse_catalog_product(data: Mapping[str, Any]) -> CatalogProduct:
    """Build the product model from the catalog product payload."""
    return CatalogProduct(
        cnk=_str_field(data, "cnk"),
        apb=_str_field(data, "apb"),
        descriptions=_descriptions_field(data.get("description")),
        brand=_str_field(data, "brand"),
        labo=_str_field(data, "labo"),
        package_code=_str_field(data, "packageCode"),
        package_quantity=_float_field(data, "packageQuantity"),
        is_on_prescription=_bool_field(data, "isOnPrescription"),
        is_medicine=_bool_field(data, "isMedicine"),
        is_own_product=_bool_field(data, "isOwnProduct"),
        price=parse_catalog_product_price(data.get("currentPriceInfo")),
        stock=parse_catalog_product_stock(data.get("currentStockInfo")),
        product_codes=_product_codes_field(data.get("productCodes")),
        raw=dict(data),
    )


def parse_catalog_products(data: Any) -> tuple[CatalogProduct, ...]:
    """Build every product from the catalog search payload."""
    if not isinstance(data, Mapping):
        return ()
    return tuple(parse_catalog_product(hit) for hit in _mapping_items(data.get("hits")))


def parse_kava_product(data: Mapping[str, Any]) -> KavaProduct:
    """Build the reimbursement model from the kava product payload."""
    return KavaProduct(
        cnk=_str_field(data, "cnk"),
        apb_product_category_code=_str_field(data, "apbProductCategoryCode"),
        is_medication=_bool_field(data, "isMedication"),
        is_veterinary_use=_bool_field(data, "isVeterinaryUse"),
        is_subject_to_repayment=_bool_field(data, "isSubjectToRepayment"),
        is_written_application=_bool_field(data, "isWrittenApplication"),
        is_on_prescription=_bool_field(data, "isOnPrescription"),
        is_fmd_product=_bool_field(data, "isFmdProduct"),
        patient_information_urls=_descriptions_field(data.get("patientInformationUrl")),
        summary_of_products_characteristics_urls=_descriptions_field(
            data.get("summaryOfProductsCharacteristicsUrl")
        ),
        raw=dict(data),
    )


def parse_service_message(data: Mapping[str, Any]) -> ServiceMessage:
    """Build one service message from its payload."""
    return ServiceMessage(
        message_nl=_str_field(data, "messageNl"),
        message_fr=_str_field(data, "messageFr"),
        priority=_int_field(data, "priority") or 0,
        scope=_str_field(data, "scope"),
        level=_str_field(data, "level"),
        raw=dict(data),
    )


def parse_service_messages(data: Any) -> tuple[ServiceMessage, ...]:
    """Build every service message from the service messages payload."""
    if not isinstance(data, Mapping):
        return ()
    return tuple(
        parse_service_message(item) for item in _mapping_items(data.get("serviceMessages"))
    )


def parse_message_draft_attachments(data: Any) -> tuple[MessageDraftAttachment, ...]:
    """Build the attachments of a draft from their payload."""
    if not isinstance(data, list):
        return ()
    return tuple(
        _parse_message_draft_attachment(item) for item in data if isinstance(item, Mapping)
    )


def _parse_message_draft_attachment(data: Mapping[str, Any]) -> MessageDraftAttachment:
    variants = data.get("variants")
    parsed: tuple[MessageDraftAttachmentVariant, ...] = ()
    if isinstance(variants, list):
        parsed = tuple(
            MessageDraftAttachmentVariant(
                type=_str_field(variant, "type"),
                media_type=_str_field(variant, "mediaType"),
                uri=_str_field(variant, "uri"),
            )
            for variant in variants
            if isinstance(variant, Mapping)
        )
    return MessageDraftAttachment(
        id=_str_field(data, "id"),
        name=_str_field(data, "name"),
        variants=parsed,
        raw=dict(data),
    )


def parse_message_draft(data: Any) -> MessageDraft | None:
    """Build the draft model from the message draft payload."""
    if not isinstance(data, Mapping):
        return None
    return MessageDraft(
        id=_str_field(data, "id"),
        reference=_str_field(data, "reference"),
        body=_str_field(data, "body"),
        attachments=parse_message_draft_attachments(data.get("attachments")),
        created_on=_datetime_field(data, "createdOn"),
        modified_on=_datetime_field(data, "modifiedOn"),
        raw=dict(data),
    )


def parse_scheme_product_entries(payload: Any) -> tuple[MedicationSchemeProductEntry, ...]:
    """Build the scheme entries of one product, keeping every entry raw."""
    if isinstance(payload, list):
        return tuple(
            MedicationSchemeProductEntry(raw=dict(item))
            for item in payload
            if isinstance(item, dict)
        )
    if isinstance(payload, dict):
        return (MedicationSchemeProductEntry(raw=dict(payload)),)
    return ()


def parse_basket_payment(payload: Any) -> BasketPayment | None:
    """Build the payment session from the pay answer, keeping the body raw."""
    if isinstance(payload, dict):
        return BasketPayment(raw=payload)
    return None


def parse_baskets(data: Mapping[str, Any]) -> tuple[CustomerBasket, ...]:
    """Build orders from the basket list payload, resolving patient names."""
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
        delivery_info = item.get("deliveryInfo")
        delivery_state = None
        delivery_location = None
        if isinstance(delivery_info, Mapping):
            delivery_state = _str_field(delivery_info, "state") or None
            delivery_location = _str_field(delivery_info, "deliveryLocation") or None
        payment_info = item.get("paymentInfo")
        payment_state = None
        total_amount = None
        if isinstance(payment_info, Mapping):
            payment_state = _str_field(payment_info, "paymentState") or None
            amount = payment_info.get("totalAmountToPay")
            total_amount = amount if isinstance(amount, int | float) else None
        baskets.append(
            CustomerBasket(
                id=_str_field(item, "id"),
                customer_patient_id=patient_id,
                customer_patient_name=embedded.get(patient_id or "") or fallback_name or None,
                state=_str_field(item, "state"),
                sales_channel=_str_field(item, "salesChannel") or None,
                comment_customer=_str_field(item, "commentCustomer") or None,
                comment_pharmacy=_str_field(item, "commentPharmacy") or None,
                delivery_state=delivery_state,
                delivery_location=delivery_location,
                payment_state=payment_state,
                total_amount_to_pay=total_amount,
                submitted_on=_datetime_field(item, "submittedOn"),
                items=parse_basket_lines(item.get("customerBasketLines")),
                raw=dict(item),
            )
        )
    return tuple(baskets)


def parse_basket_lines(data: Any) -> tuple[BasketLine, ...]:
    """Build order lines from the customerBasketLines payload."""
    if not isinstance(data, list):
        return ()
    lines: list[BasketLine] = []
    for line in data:
        if not isinstance(line, Mapping):
            continue
        product = line.get("product")
        description_nl = ""
        description_fr = ""
        cnk = ""
        if isinstance(product, Mapping):
            cnk = _str_field(product, "cnk")
            description = product.get("description")
            if isinstance(description, Mapping):
                description_nl = _str_field(description, "nl")
                description_fr = _str_field(description, "fr")
        unit_price = line.get("unitPrice")
        lines.append(
            BasketLine(
                cnk=cnk,
                description_nl=description_nl,
                description_fr=description_fr,
                quantity_ordered=_int_field(line, "quantityOrdered") or 0,
                unit_price=unit_price if isinstance(unit_price, int | float) else None,
            )
        )
    return tuple(lines)


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
