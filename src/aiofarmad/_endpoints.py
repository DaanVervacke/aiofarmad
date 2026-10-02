"""The frozen endpoint catalog: one row per wire contract."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import aiohttp

from .const import ALB_BASE_URL, CATALOG_BASE_URL, EHEALTH_BASE_URL
from .models import (
    BasketPayment,
    CatalogProduct,
    ConversationSummary,
    CustomerBasket,
    DraftBasket,
    DraftProduct,
    FarmadAccount,
    FarmadMessage,
    FarmadPatient,
    KavaProduct,
    MedicationDayScheme,
    MedicationNondailyProduct,
    MedicationSchemeProductEntry,
    MessageDraft,
    Pharmacy,
    PharmacyPreferences,
    Prescription,
    ServiceMessage,
)
from .parsers import (
    parse_account,
    parse_basket_payment,
    parse_baskets,
    parse_catalog_product,
    parse_catalog_products,
    parse_conversations,
    parse_day_scheme_range,
    parse_draft_basket,
    parse_kava_product,
    parse_message,
    parse_message_draft,
    parse_nondaily_products,
    parse_organization,
    parse_patient,
    parse_pharmacy_preferences,
    parse_prescription,
    parse_prescriptions,
    parse_scheme_product_entries,
    parse_service_messages,
)

DEFAULT_LANGUAGE = "nl"
DEFAULT_PAGE_LIMIT = 25


@dataclass(frozen=True, slots=True)
class AccountArgs:
    """The account to act on."""

    account_id: str


@dataclass(frozen=True, slots=True)
class PharmacyArgs:
    """One pharmacy, addressed by its apb number."""

    apb: str

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PatientArgs:
    """One patient, addressed by its patient id."""

    patient_id: str

    def __post_init__(self) -> None:
        if not self.patient_id:
            msg = "patient_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SchemeDayArgs(PatientArgs):
    """A day scheme window for one patient at one pharmacy."""

    apb: str
    from_: datetime
    until: datetime
    language: str = DEFAULT_LANGUAGE

    def __post_init__(self) -> None:
        if not self.patient_id:
            msg = "patient_id must not be empty"
            raise ValueError(msg)
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        for stamp in (self.from_, self.until):
            if stamp.tzinfo is None:
                msg = "timezone-aware datetimes required"
                raise ValueError(msg)
        if self.from_ > self.until:
            msg = "from_ must not be later than until"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SchemeNondailyArgs(PatientArgs):
    """A nondaily scheme for one patient at one pharmacy."""

    apb: str
    day: date
    language: str = DEFAULT_LANGUAGE

    def __post_init__(self) -> None:
        if not self.patient_id:
            msg = "patient_id must not be empty"
            raise ValueError(msg)
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SchemeProductArgs(PatientArgs):
    """The scheme entries of one product for one patient at one pharmacy."""

    apb: str
    cnk: str
    language: str = DEFAULT_LANGUAGE

    def __post_init__(self) -> None:
        if not self.patient_id:
            msg = "patient_id must not be empty"
            raise ValueError(msg)
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.cnk:
            msg = "cnk must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ConversationsArgs(PharmacyArgs):
    """One page of conversations at one pharmacy."""

    limit: int = DEFAULT_PAGE_LIMIT
    page: int = 0

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if self.limit < 1 or self.page < 0:
            msg = "limit must be positive and page must not be negative"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ConversationMessagesArgs(ConversationsArgs):
    """One page of messages in one conversation."""

    customer_account_id: str = ""

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if self.limit < 1 or self.page < 0:
            msg = "limit must be positive and page must not be negative"
            raise ValueError(msg)
        if not self.customer_account_id:
            msg = "customer_account_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class BasketsArgs(PharmacyArgs):
    """One page of baskets for one patient at one pharmacy."""

    patient_id: str
    skip: int = 0
    take: int = 50

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.patient_id:
            msg = "patient_id must not be empty"
            raise ValueError(msg)
        if self.skip < 0 or self.take < 1:
            msg = "skip must not be negative and take must be positive"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DraftArgs(PharmacyArgs):
    """The draft basket of one account at one pharmacy."""

    account_id: str

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.account_id:
            msg = "account_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DraftWriteArgs(DraftArgs):
    """The body for creating a draft basket."""

    patient_id: str
    products: tuple[DraftProduct, ...] = ()

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.account_id:
            msg = "account_id must not be empty"
            raise ValueError(msg)
        if not self.patient_id:
            msg = "patient_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DraftUpdateArgs(DraftArgs):
    """The body for replacing the product lines of an existing draft basket."""

    patient_id: str
    basket_id: str
    products: tuple[DraftProduct, ...] = ()

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.account_id:
            msg = "account_id must not be empty"
            raise ValueError(msg)
        if not self.patient_id:
            msg = "patient_id must not be empty"
            raise ValueError(msg)
        if not self.basket_id:
            msg = "basket_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SubmitBasketArgs(PharmacyArgs):
    """The body for submitting a draft basket as an order."""

    basket_id: str
    patient_id: str
    products: tuple[DraftProduct, ...] = ()
    comment: str | None = None
    unit_prices: tuple[tuple[str, float], ...] = ()
    pay_online: bool = False

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.basket_id:
            msg = "basket_id must not be empty"
            raise ValueError(msg)
        if not self.patient_id:
            msg = "patient_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class BasketIdArgs(PharmacyArgs):
    """One basket, addressed by its id."""

    basket_id: str

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.basket_id:
            msg = "basket_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PayBasketArgs(PharmacyArgs):
    """The body for starting an online payment of one submitted order."""

    basket_id: str
    redirect_url: str

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.basket_id:
            msg = "basket_id must not be empty"
            raise ValueError(msg)
        if not self.redirect_url:
            msg = "redirect_url must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SelfOnboardingArgs(AccountArgs):
    """The pharmacy to link to the account through self-onboarding."""

    apb: str

    def __post_init__(self) -> None:
        if not self.account_id:
            msg = "account_id must not be empty"
            raise ValueError(msg)
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PrescriptionsArgs:
    """One page of prescriptions."""

    page: int = 0
    language: str = "nl"

    def __post_init__(self) -> None:
        if self.page < 0:
            msg = "page must not be negative"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PrescriptionArgs:
    """One prescription, addressed by its Recip-e id."""

    prescription_id: str
    language: str = "nl"

    def __post_init__(self) -> None:
        if not self.prescription_id:
            msg = "prescription_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Endpoint[ArgsT, ModelT]:
    """One wire contract: method, url, params, body, and the parse step."""

    name: str
    method: str
    url: Callable[[ArgsT], str]
    version: str
    parse: Callable[[Any, ArgsT], ModelT]
    params: Callable[[ArgsT], dict[str, str]]
    base_url: str = ALB_BASE_URL
    json_body: Callable[[ArgsT], dict[str, Any]] | None = None
    form_body: Callable[[ArgsT], aiohttp.FormData] | None = None
    not_found_is_none: bool = False
    ehealth: bool = False


def _draft_products(products: tuple[DraftProduct, ...], patient_id: str) -> list[dict[str, Any]]:
    return [
        {
            "productCnk": product.product_cnk,
            "quantityOrdered": product.quantity,
            "patientId": patient_id,
        }
        for product in products
    ]


ACCOUNT: Endpoint[AccountArgs, FarmadAccount] = Endpoint(
    name="account",
    method="GET",
    url=lambda args: f"/usermanagement/api/account/{args.account_id}",
    version="8.12",
    params=lambda _args: {},
    parse=lambda payload, _args: parse_account(payload),
)

ORGANIZATION: Endpoint[PharmacyArgs, Pharmacy] = Endpoint(
    name="organization",
    method="GET",
    url=lambda args: f"/usermanagement/api/organization/{args.apb}",
    version="8.12",
    params=lambda _args: {},
    parse=lambda payload, _args: parse_organization(payload),
)

PATIENT: Endpoint[PatientArgs, FarmadPatient] = Endpoint(
    name="patient",
    method="GET",
    url=lambda args: f"/patientmanagement/api/patients/{args.patient_id}",
    version="2.0",
    params=lambda _args: {},
    parse=lambda payload, _args: parse_patient(payload),
)

PHARMACY_PREFERENCES: Endpoint[PharmacyArgs, PharmacyPreferences] = Endpoint(
    name="pharmacy_preferences",
    method="GET",
    url=lambda args: f"/customerbasket/api/{args.apb}/pharmacypreferences/for-customer",
    version="1.0",
    params=lambda _args: {},
    parse=lambda payload, _args: parse_pharmacy_preferences(payload),
)

SCHEME_DAY: Endpoint[SchemeDayArgs, tuple[MedicationDayScheme, ...]] = Endpoint(
    name="scheme_day",
    method="GET",
    url=lambda args: (
        f"/medicationscheme/api/medicationscheme/{args.patient_id}/scheme/{args.apb}/day"
    ),
    version="2.5",
    params=lambda args: {
        "from": args.from_.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "until": args.until.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "language": args.language,
    },
    parse=lambda payload, _args: parse_day_scheme_range(payload),
)

SCHEME_NONDAILY: Endpoint[SchemeNondailyArgs, tuple[MedicationNondailyProduct, ...]] = Endpoint(
    name="scheme_nondaily",
    method="GET",
    url=lambda args: (
        f"/medicationscheme/api/medicationscheme/{args.patient_id}/scheme/{args.apb}/nondaily"
    ),
    version="2.5",
    params=lambda args: {
        "day": f"{args.day.isoformat()}T00:00:00.000Z",
        "language": args.language,
    },
    parse=lambda payload, _args: parse_nondaily_products(payload),
)

SCHEME_PRODUCT: Endpoint[SchemeProductArgs, tuple[MedicationSchemeProductEntry, ...]] = Endpoint(
    name="scheme_product",
    method="GET",
    url=lambda args: (
        f"/medicationscheme/api/medicationscheme/{args.patient_id}"
        f"/scheme/{args.apb}/product/{args.cnk}"
    ),
    version="2.5",
    params=lambda args: {"language": args.language},
    parse=lambda payload, _args: parse_scheme_product_entries(payload),
)

CONVERSATIONS: Endpoint[ConversationsArgs, tuple[ConversationSummary, ...]] = Endpoint(
    name="conversations",
    method="GET",
    url=lambda args: f"/messaging/api/message/{args.apb}",
    version="4.0",
    params=lambda args: {"Limit": str(args.limit), "Page": str(args.page)},
    parse=lambda payload, _args: parse_conversations(payload),
)

CONVERSATION_MESSAGES: Endpoint[ConversationMessagesArgs, tuple[FarmadMessage, ...]] = Endpoint(
    name="conversation_messages",
    method="GET",
    url=lambda args: f"/messaging/api/message/{args.apb}/{args.customer_account_id}",
    version="4.0",
    params=lambda args: {"Limit": str(args.limit), "Page": str(args.page)},
    parse=lambda payload, _args: _parse_messages(payload),
)

BASKETS: Endpoint[BasketsArgs, tuple[CustomerBasket, ...]] = Endpoint(
    name="baskets",
    method="GET",
    url=lambda args: f"/customerbasket/api/{args.apb}/customerbaskets",
    version="1.0",
    params=lambda args: {
        "PatientId": args.patient_id,
        "Skip": str(args.skip),
        "Take": str(args.take),
    },
    parse=lambda payload, _args: parse_baskets(payload),
)

DRAFT_BASKET: Endpoint[DraftArgs, DraftBasket | None] = Endpoint(
    name="draft_basket",
    method="GET",
    url=lambda args: f"/customerbasket/api/{args.apb}/drafts/{args.account_id}",
    version="1.0",
    params=lambda _args: {},
    parse=lambda payload, _args: parse_draft_basket(payload) if isinstance(payload, dict) else None,
    not_found_is_none=True,
)

DRAFT_SAVE: Endpoint[DraftWriteArgs, str | None] = Endpoint(
    name="draft_save",
    method="POST",
    url=lambda args: f"/customerbasket/api/{args.apb}/drafts/{args.account_id}",
    version="1.0",
    params=lambda _args: {},
    json_body=lambda args: {
        "patientId": args.patient_id,
        "products": _draft_products(args.products, args.patient_id),
    },
    parse=lambda payload, _args: _optional_id(payload),
)

DRAFT_UPDATE: Endpoint[DraftUpdateArgs, str | None] = Endpoint(
    name="draft_update",
    method="PATCH",
    url=lambda args: f"/customerbasket/api/{args.apb}/drafts/{args.account_id}/{args.basket_id}",
    version="1.0",
    params=lambda _args: {},
    json_body=lambda args: {
        "patientId": args.patient_id,
        "products": _draft_products(args.products, args.patient_id),
    },
    parse=lambda payload, _args: _optional_id(payload),
)

DRAFT_CLEAR: Endpoint[DraftArgs, None] = Endpoint(
    name="draft_clear",
    method="DELETE",
    url=lambda args: f"/customerbasket/api/{args.apb}/drafts/{args.account_id}",
    version="1.0",
    params=lambda _args: {},
    parse=lambda _payload, _args: None,
)

SUBMIT_BASKET: Endpoint[SubmitBasketArgs, str | None] = Endpoint(
    name="submit_basket",
    method="PATCH",
    url=lambda args: f"/customerbasket/api/{args.apb}/customerbaskets/{args.basket_id}/submit",
    version="1.0",
    params=lambda _args: {},
    json_body=lambda args: {
        "patientId": args.patient_id,
        "commentCustomer": args.comment,
        "products": _draft_products(args.products, args.patient_id),
        "unitPrices": [{"productCnk": cnk, "price": price} for cnk, price in args.unit_prices],
        "preferPaymentAtPickup": not args.pay_online,
        "redirectUrl": None,
    },
    parse=lambda payload, _args: _optional_id(payload),
)

CANCEL_BASKET: Endpoint[BasketIdArgs, None] = Endpoint(
    name="cancel_basket",
    method="PUT",
    url=lambda args: f"/customerbasket/api/{args.apb}/customerbaskets/{args.basket_id}/cancel",
    version="1.0",
    params=lambda _args: {},
    parse=lambda _payload, _args: None,
)

PAY_BASKET: Endpoint[PayBasketArgs, BasketPayment | None] = Endpoint(
    name="pay_basket",
    method="POST",
    url=lambda args: f"/customerbasket/api/{args.apb}/customerbaskets/{args.basket_id}/pay",
    version="1.0",
    params=lambda _args: {},
    json_body=lambda args: {"redirectUrl": args.redirect_url},
    parse=lambda payload, _args: parse_basket_payment(payload),
)


@dataclass(frozen=True, slots=True)
class ProductInApbArgs:
    """One product at one pharmacy, addressed by its CNK."""

    cnk: str
    apb: str

    def __post_init__(self) -> None:
        if not self.cnk:
            msg = "cnk must not be empty"
            raise ValueError(msg)
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ProductInApbByGtinArgs:
    """One product at one pharmacy, addressed by its GTIN barcode."""

    gtin: str
    apb: str

    def __post_init__(self) -> None:
        if not self.gtin:
            msg = "gtin must not be empty"
            raise ValueError(msg)
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SearchProductsArgs:
    """One page of search results in the catalog of one pharmacy."""

    apb: str
    query: str
    language: str = DEFAULT_LANGUAGE
    limit: int = DEFAULT_PAGE_LIMIT
    page: int = 1

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.query:
            msg = "query must not be empty"
            raise ValueError(msg)
        if self.limit < 1 or self.page < 1:
            msg = "limit and page must be positive"
            raise ValueError(msg)


PRODUCT_IN_APB: Endpoint[ProductInApbArgs, CatalogProduct | None] = Endpoint(
    name="product_in_apb",
    method="GET",
    url=lambda args: f"/api/catalog/products/{args.cnk}/{args.apb}",
    version="5.3",
    base_url=CATALOG_BASE_URL,
    params=lambda _args: {},
    parse=lambda payload, _args: (
        parse_catalog_product(payload) if isinstance(payload, dict) else None
    ),
    not_found_is_none=True,
)

PRODUCT_IN_APB_BY_GTIN: Endpoint[ProductInApbByGtinArgs, CatalogProduct | None] = Endpoint(
    name="product_in_apb_by_gtin",
    method="GET",
    url=lambda args: f"/api/catalog/products/gtin/{args.gtin}/{args.apb}",
    version="5.3",
    base_url=CATALOG_BASE_URL,
    params=lambda _args: {},
    parse=lambda payload, _args: (
        parse_catalog_product(payload) if isinstance(payload, dict) else None
    ),
    not_found_is_none=True,
)

SEARCH_PRODUCTS: Endpoint[SearchProductsArgs, tuple[CatalogProduct, ...]] = Endpoint(
    name="search_products",
    method="GET",
    url=lambda _args: "/api/catalog/products",
    version="5.3",
    base_url=CATALOG_BASE_URL,
    params=lambda args: {
        "SearchTerm": args.query,
        "Apb": args.apb,
        "Page": str(args.page),
        "Limit": str(args.limit),
        "Language": args.language,
    },
    parse=lambda payload, _args: parse_catalog_products(payload),
)


@dataclass(frozen=True, slots=True)
class KavaProductArgs:
    """The reimbursement data of one product, addressed by its CNK."""

    cnk: str

    def __post_init__(self) -> None:
        if not self.cnk:
            msg = "cnk must not be empty"
            raise ValueError(msg)


KAVA_PRODUCT: Endpoint[KavaProductArgs, KavaProduct] = Endpoint(
    name="kava_product",
    method="GET",
    url=lambda args: f"/api/catalog/products/kava/{args.cnk}",
    version="5.3",
    base_url=CATALOG_BASE_URL,
    params=lambda _args: {},
    parse=lambda payload, _args: parse_kava_product(payload),
)


@dataclass(frozen=True, slots=True)
class MessageDraftArgs(PharmacyArgs):
    """The message draft of one account at one pharmacy."""

    account_id: str

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.account_id:
            msg = "account_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class MessageDraftSaveArgs(MessageDraftArgs):
    """The body for creating a message draft."""

    body: str
    reference: str = ""


@dataclass(frozen=True, slots=True)
class MessageDraftIdArgs(MessageDraftArgs):
    """One message draft of one account, addressed by its id."""

    draft_id: str

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.account_id:
            msg = "account_id must not be empty"
            raise ValueError(msg)
        if not self.draft_id:
            msg = "draft_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class MessageDraftUpdateArgs(MessageDraftIdArgs):
    """The body for replacing the text of an existing message draft."""

    body: str
    reference: str = ""


@dataclass(frozen=True, slots=True)
class MessageAttachmentUploadArgs(MessageDraftIdArgs):
    """One file to attach to a message draft."""

    filename: str
    content: bytes
    content_type: str = "application/pdf"

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.account_id:
            msg = "account_id must not be empty"
            raise ValueError(msg)
        if not self.draft_id:
            msg = "draft_id must not be empty"
            raise ValueError(msg)
        if not self.filename:
            msg = "filename must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class MessageAttachmentDeleteArgs(MessageDraftArgs):
    """One attachment of a message draft, addressed by its id."""

    attachment_id: str

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.account_id:
            msg = "account_id must not be empty"
            raise ValueError(msg)
        if not self.attachment_id:
            msg = "attachment_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class MessageMarkReadArgs(MessageDraftArgs):
    """One message of one account, addressed by its id."""

    message_id: str

    def __post_init__(self) -> None:
        if not self.apb:
            msg = "apb must not be empty"
            raise ValueError(msg)
        if not self.account_id:
            msg = "account_id must not be empty"
            raise ValueError(msg)
        if not self.message_id:
            msg = "message_id must not be empty"
            raise ValueError(msg)


def _attachment_form(args: MessageAttachmentUploadArgs) -> aiohttp.FormData:
    form = aiohttp.FormData()
    form.add_field(
        "uploadedFile", args.content, filename=args.filename, content_type=args.content_type
    )
    return form


MESSAGE_DRAFT: Endpoint[MessageDraftArgs, MessageDraft | None] = Endpoint(
    name="message_draft",
    method="GET",
    url=lambda args: f"/messaging/api/draft/{args.apb}/{args.account_id}",
    version="4.0",
    params=lambda _args: {},
    parse=lambda payload, _args: parse_message_draft(payload),
    not_found_is_none=True,
)

MESSAGE_DRAFT_SAVE: Endpoint[MessageDraftSaveArgs, MessageDraft | None] = Endpoint(
    name="message_draft_save",
    method="POST",
    url=lambda args: f"/messaging/api/draft/{args.apb}/{args.account_id}",
    version="4.0",
    params=lambda _args: {},
    json_body=lambda args: {"body": args.body, "reference": args.reference},
    parse=lambda payload, _args: parse_message_draft(payload),
)

MESSAGE_DRAFT_UPDATE: Endpoint[MessageDraftUpdateArgs, None] = Endpoint(
    name="message_draft_update",
    method="PUT",
    url=lambda args: f"/messaging/api/draft/{args.apb}/{args.account_id}/{args.draft_id}",
    version="4.0",
    params=lambda _args: {},
    json_body=lambda args: {"body": args.body, "reference": args.reference},
    parse=lambda _payload, _args: None,
)

MESSAGE_DRAFT_SEND: Endpoint[MessageDraftIdArgs, None] = Endpoint(
    name="message_draft_send",
    method="POST",
    url=lambda args: f"/messaging/api/draft/{args.apb}/{args.account_id}/send/{args.draft_id}",
    version="4.0",
    params=lambda _args: {},
    parse=lambda _payload, _args: None,
)

MESSAGE_ATTACHMENT_UPLOAD: Endpoint[MessageAttachmentUploadArgs, str | None] = Endpoint(
    name="message_attachment_upload",
    method="POST",
    url=lambda args: (
        f"/messaging/api/draft/{args.apb}/{args.account_id}/{args.draft_id}/attachment"
    ),
    version="4.0",
    params=lambda _args: {},
    form_body=_attachment_form,
    parse=lambda payload, _args: _optional_attachment_id(payload),
)

MESSAGE_ATTACHMENT_DELETE: Endpoint[MessageAttachmentDeleteArgs, None] = Endpoint(
    name="message_attachment_delete",
    method="DELETE",
    url=lambda args: (
        f"/messaging/api/draft/{args.apb}/{args.account_id}/attachment/{args.attachment_id}"
    ),
    version="4.0",
    params=lambda _args: {},
    parse=lambda _payload, _args: None,
)

MESSAGE_MARK_READ: Endpoint[MessageMarkReadArgs, None] = Endpoint(
    name="message_mark_read",
    method="PUT",
    url=lambda args: f"/messaging/api/message/{args.apb}/{args.account_id}/{args.message_id}",
    version="4.0",
    params=lambda _args: {},
    parse=lambda _payload, _args: None,
)


@dataclass(frozen=True, slots=True)
class PlatformArgs:
    """No request parameters: the platform status reads take none."""


SERVICE_MESSAGES: Endpoint[PlatformArgs, tuple[ServiceMessage, ...]] = Endpoint(
    name="service_messages",
    method="GET",
    url=lambda _args: "/notifications/api/servicemessages",
    version="2.1",
    params=lambda _args: {},
    parse=lambda payload, _args: parse_service_messages(payload),
)

TECHNICAL_INTERRUPTIONS: Endpoint[PlatformArgs, bool] = Endpoint(
    name="technical_interruptions",
    method="GET",
    url=lambda _args: "/notifications/api/technicalinterruptions",
    version="2.1",
    params=lambda _args: {},
    parse=lambda payload, _args: payload is True,
)


_EHEALTH_HOST = EHEALTH_BASE_URL.removesuffix("/ehealth")

PRESCRIPTIONS: Endpoint[PrescriptionsArgs, tuple[Prescription, ...]] = Endpoint(
    name="prescriptions",
    method="GET",
    url=lambda _args: "/ehealth/api/prescriptions",
    version="1.1",
    base_url=_EHEALTH_HOST,
    params=lambda args: {"page": str(args.page), "language": args.language},
    parse=lambda payload, _args: parse_prescriptions(payload),
    ehealth=True,
)

PRESCRIPTION: Endpoint[PrescriptionArgs, Prescription | None] = Endpoint(
    name="prescription",
    method="GET",
    url=lambda args: f"/ehealth/api/prescriptions/{args.prescription_id}",
    version="1.1",
    base_url=_EHEALTH_HOST,
    params=lambda args: {"language": args.language},
    parse=lambda payload, args: parse_prescription(payload, args.prescription_id),
    not_found_is_none=True,
    ehealth=True,
)


def _parse_messages(payload: Any) -> tuple[FarmadMessage, ...]:
    if not isinstance(payload, list):
        return ()
    return tuple(parse_message(item) for item in payload if isinstance(item, dict))


def _optional_id(payload: Any) -> str | None:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        value = payload.get("id")
        if isinstance(value, str):
            return value
    return None


def _optional_attachment_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        value = payload.get("attachmentId")
        if isinstance(value, str):
            return value
    return None


def _accept_ok(_payload: Any, _args: Any) -> bool:
    return True


SELF_ONBOARDING: Endpoint[SelfOnboardingArgs, bool] = Endpoint(
    name="self_onboarding",
    method="POST",
    url=lambda args: f"/usermanagement/api/account/{args.account_id}/self-onboarding",
    version="8.12",
    params=lambda _args: {},
    json_body=lambda args: {"apb": args.apb},
    parse=_accept_ok,
)
