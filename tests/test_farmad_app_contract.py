"""Contract tests against the pinned Mijn Farmad app bundle."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from aiofarmad._endpoints import (
    ACCOUNT,
    BASKETS,
    CANCEL_BASKET,
    CONVERSATION_MESSAGES,
    CONVERSATIONS,
    DRAFT_BASKET,
    DRAFT_CLEAR,
    DRAFT_SAVE,
    DRAFT_UPDATE,
    KAVA_PRODUCT,
    MESSAGE_ATTACHMENT_DELETE,
    MESSAGE_ATTACHMENT_UPLOAD,
    MESSAGE_DRAFT,
    MESSAGE_DRAFT_SAVE,
    MESSAGE_DRAFT_SEND,
    MESSAGE_DRAFT_UPDATE,
    MESSAGE_MARK_READ,
    ORGANIZATION,
    PATIENT,
    PAY_BASKET,
    PHARMACY_PREFERENCES,
    PRESCRIPTION,
    PRESCRIPTIONS,
    PRODUCT_IN_APB,
    PRODUCT_IN_APB_BY_GTIN,
    SCHEME_DAY,
    SCHEME_NONDAILY,
    SCHEME_PRODUCT,
    SEARCH_PRODUCTS,
    SELF_ONBOARDING,
    SERVICE_MESSAGES,
    SUBMIT_BASKET,
    TECHNICAL_INTERRUPTIONS,
    AccountArgs,
    BasketIdArgs,
    BasketsArgs,
    ConversationMessagesArgs,
    ConversationsArgs,
    DraftArgs,
    DraftUpdateArgs,
    DraftWriteArgs,
    Endpoint,
    KavaProductArgs,
    MessageAttachmentDeleteArgs,
    MessageAttachmentUploadArgs,
    MessageDraftArgs,
    MessageDraftIdArgs,
    MessageDraftSaveArgs,
    MessageDraftUpdateArgs,
    MessageMarkReadArgs,
    PatientArgs,
    PayBasketArgs,
    PharmacyArgs,
    PlatformArgs,
    PrescriptionArgs,
    PrescriptionsArgs,
    ProductInApbArgs,
    ProductInApbByGtinArgs,
    SchemeDayArgs,
    SchemeNondailyArgs,
    SchemeProductArgs,
    SearchProductsArgs,
    SelfOnboardingArgs,
    SubmitBasketArgs,
)

FIXTURE = Path(__file__).parent / "fixtures" / "farmad_app_contract.json"

ENDPOINTS: tuple[Endpoint[Any, Any], ...] = (
    ACCOUNT,
    ORGANIZATION,
    PATIENT,
    PHARMACY_PREFERENCES,
    PRESCRIPTION,
    PRESCRIPTIONS,
    PRODUCT_IN_APB,
    PRODUCT_IN_APB_BY_GTIN,
    KAVA_PRODUCT,
    SEARCH_PRODUCTS,
    MESSAGE_DRAFT,
    MESSAGE_DRAFT_SAVE,
    MESSAGE_DRAFT_UPDATE,
    MESSAGE_DRAFT_SEND,
    MESSAGE_ATTACHMENT_UPLOAD,
    MESSAGE_ATTACHMENT_DELETE,
    MESSAGE_MARK_READ,
    SERVICE_MESSAGES,
    TECHNICAL_INTERRUPTIONS,
    SCHEME_DAY,
    SCHEME_NONDAILY,
    SCHEME_PRODUCT,
    CONVERSATIONS,
    CONVERSATION_MESSAGES,
    BASKETS,
    DRAFT_BASKET,
    DRAFT_SAVE,
    DRAFT_UPDATE,
    DRAFT_CLEAR,
    SUBMIT_BASKET,
    CANCEL_BASKET,
    PAY_BASKET,
    SELF_ONBOARDING,
)


WINDOW_START = datetime(2026, 10, 1, tzinfo=UTC)
WINDOW_END = datetime(2026, 10, 7, tzinfo=UTC)


def dummy_args(endpoint: Endpoint[Any, Any]) -> object:
    return {
        "account": AccountArgs(account_id="id"),
        "organization": PharmacyArgs(apb="apb"),
        "patient": PatientArgs(patient_id="patientId"),
        "pharmacy_preferences": PharmacyArgs(apb="apb"),
        "scheme_day": SchemeDayArgs(
            apb="apb", patient_id="patientId", from_=WINDOW_START, until=WINDOW_END
        ),
        "scheme_nondaily": SchemeNondailyArgs(
            apb="apb", patient_id="patientId", day=date(2026, 10, 1)
        ),
        "scheme_product": SchemeProductArgs(apb="apb", cnk="cnk", patient_id="patientId"),
        "conversations": ConversationsArgs(apb="apb"),
        "conversation_messages": ConversationMessagesArgs(
            apb="apb", customer_account_id="customerAccountId"
        ),
        "baskets": BasketsArgs(apb="apb", patient_id="patientId"),
        "draft_basket": DraftArgs(apb="apb", account_id="accountId"),
        "draft_save": DraftWriteArgs(apb="apb", account_id="accountId", patient_id="patientId"),
        "draft_update": DraftUpdateArgs(
            apb="apb", account_id="accountId", patient_id="patientId", basket_id="basketId"
        ),
        "draft_clear": DraftArgs(apb="apb", account_id="accountId"),
        "submit_basket": SubmitBasketArgs(apb="apb", basket_id="basketId", patient_id="patientId"),
        "cancel_basket": BasketIdArgs(apb="apb", basket_id="basketId"),
        "pay_basket": PayBasketArgs(apb="apb", basket_id="basketId", redirect_url="https://x/"),
        "self_onboarding": SelfOnboardingArgs(account_id="id", apb="apb"),
        "product_in_apb": ProductInApbArgs(cnk="cnk", apb="apb"),
        "product_in_apb_by_gtin": ProductInApbByGtinArgs(gtin="gtin", apb="apb"),
        "search_products": SearchProductsArgs(apb="apb", query="query"),
        "kava_product": KavaProductArgs(cnk="cnk"),
        "message_draft": MessageDraftArgs(apb="apb", account_id="customerAccountId"),
        "message_draft_save": MessageDraftSaveArgs(
            apb="apb", account_id="customerAccountId", body=""
        ),
        "message_draft_update": MessageDraftUpdateArgs(
            apb="apb", account_id="customerAccountId", draft_id="draftId", body=""
        ),
        "message_draft_send": MessageDraftIdArgs(
            apb="apb", account_id="customerAccountId", draft_id="draftId"
        ),
        "message_attachment_upload": MessageAttachmentUploadArgs(
            apb="apb",
            account_id="customerAccountId",
            draft_id="draftId",
            filename="f.txt",
            content=b"x",
        ),
        "message_attachment_delete": MessageAttachmentDeleteArgs(
            apb="apb", account_id="customerAccountId", attachment_id="attachmentId"
        ),
        "message_mark_read": MessageMarkReadArgs(
            apb="apb", account_id="customerAccountId", message_id="messageId"
        ),
        "service_messages": PlatformArgs(),
        "technical_interruptions": PlatformArgs(),
        "prescriptions": PrescriptionsArgs(page=0),
        "prescription": PrescriptionArgs(prescription_id="id"),
    }[endpoint.name]


@pytest.fixture
def contract() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(FIXTURE.read_text()))


def test_contract_pins_the_evidence(contract: dict[str, Any]) -> None:
    source = contract["source"]
    assert source["appVersion"] == "2.2.8"
    assert source["appPackageId"] == "be.farmad.procura.prod"
    assert source["bundleBuild"] == "13237"
    assert source["bundleFile"] == "main.2ba421e258d1f7c6.js"


def test_every_library_endpoint_is_in_the_contract(contract: dict[str, Any]) -> None:
    contract_names = {row["name"] for row in contract["endpoints"]}
    library_names = {endpoint.name for endpoint in ENDPOINTS}
    assert contract_names == library_names


PLACEHOLDERS = {
    "id": "id",
    "apb": "apb",
    "patientId": "patientId",
    "customerAccountId": "customerAccountId",
    "accountId": "accountId",
    "basketId": "basketId",
    "prescriptionId": "prescriptionId",
    "cnk": "cnk",
    "gtin": "gtin",
    "draftId": "draftId",
    "attachmentId": "attachmentId",
    "messageId": "messageId",
}


def test_wire_paths_match_the_app(contract: dict[str, Any]) -> None:
    rows = {row["name"]: row for row in contract["endpoints"]}
    for endpoint in ENDPOINTS:
        row = rows[endpoint.name]
        prefix = f"/{row['service']}" if row.get("gateway", True) else ""
        path = f"{prefix}{row['path']}"
        for placeholder, value in PLACEHOLDERS.items():
            path = path.replace("{" + placeholder + "}", value)
        rendered = endpoint.url(dummy_args(endpoint))
        assert rendered == path, f"{endpoint.name} drifted: {rendered} != {path}"


def test_versions_match_the_app(contract: dict[str, Any]) -> None:
    rows = {row["name"]: row for row in contract["endpoints"]}
    for endpoint in ENDPOINTS:
        assert endpoint.version == rows[endpoint.name]["version"], endpoint.name


def test_methods_match_the_app(contract: dict[str, Any]) -> None:
    rows = {row["name"]: row for row in contract["endpoints"]}
    for endpoint in ENDPOINTS:
        assert endpoint.method == rows[endpoint.name]["method"], endpoint.name


def test_ledger_pins_its_size(contract: dict[str, Any]) -> None:
    ledger = contract["ledger"]
    rows = ledger["rows"]
    assert ledger["bundle"] == contract["source"]["bundleFile"]
    assert len(rows) == ledger["pathCount"]
    paths = [row["path"] for row in rows]
    assert len(paths) == len(set(paths))


def test_ledger_classifies_only_known_statuses(contract: dict[str, Any]) -> None:
    for row in contract["ledger"]["rows"]:
        assert row["status"] in {"implemented", "waived"}, row["path"]
        if row["status"] == "implemented":
            assert row["names"], row["path"]
        else:
            assert row["reason"], row["path"]


def test_ledger_covers_every_endpoint(contract: dict[str, Any]) -> None:
    ledger_by_path = {row["path"]: row for row in contract["ledger"]["rows"]}
    endpoint_rows = {row["name"]: row for row in contract["endpoints"]}
    for name, endpoint_row in endpoint_rows.items():
        row = ledger_by_path[endpoint_row["path"]]
        assert row["status"] == "implemented", name
        assert name in row["names"], name


def test_ledger_names_match_the_endpoint_catalog(contract: dict[str, Any]) -> None:
    ledger_names = {
        name
        for row in contract["ledger"]["rows"]
        if row["status"] == "implemented"
        for name in row["names"]
    }
    endpoint_names = {endpoint.name for endpoint in ENDPOINTS}
    assert ledger_names == endpoint_names
