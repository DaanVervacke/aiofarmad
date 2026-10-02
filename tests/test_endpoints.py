"""Endpoint catalog tests: arg validation and body builders."""

from datetime import UTC, date, datetime

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
    BasketIdArgs,
    BasketsArgs,
    ConversationMessagesArgs,
    ConversationsArgs,
    DraftArgs,
    DraftUpdateArgs,
    DraftWriteArgs,
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
    _optional_attachment_id,
    _optional_id,
    _parse_messages,
)
from aiofarmad.models import DraftProduct

START = datetime(2026, 10, 1, tzinfo=UTC)
END = datetime(2026, 10, 7, tzinfo=UTC)


def test_pharmacy_args_rejects_empty_apb() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        PharmacyArgs(apb="")


def test_patient_args_rejects_empty_patient() -> None:
    with pytest.raises(ValueError, match="patient_id must not be empty"):
        PatientArgs(patient_id="")


def test_scheme_day_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        SchemeDayArgs(apb="", patient_id="p", from_=START, until=END)
    with pytest.raises(ValueError, match="patient_id must not be empty"):
        SchemeDayArgs(apb="a", patient_id="", from_=START, until=END)
    with pytest.raises(ValueError, match="timezone-aware"):
        SchemeDayArgs(
            apb="a",
            patient_id="p",
            from_=datetime(2026, 10, 1),  # noqa: DTZ001
            until=END,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        SchemeDayArgs(
            apb="a",
            patient_id="p",
            from_=START,
            until=datetime(2026, 10, 7),  # noqa: DTZ001
        )
    with pytest.raises(ValueError, match="from_ must not be later than until"):
        SchemeDayArgs(apb="a", patient_id="p", from_=END, until=START)


def test_scheme_nondaily_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        SchemeNondailyArgs(apb="", patient_id="p", day=date(2026, 10, 1))
    with pytest.raises(ValueError, match="patient_id must not be empty"):
        SchemeNondailyArgs(apb="a", patient_id="", day=date(2026, 10, 1))


def test_conversations_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        ConversationsArgs(apb="", limit=10, page=0)
    with pytest.raises(ValueError, match="limit must be positive"):
        ConversationsArgs(apb="a", limit=0, page=0)
    with pytest.raises(ValueError, match="page must not be negative"):
        ConversationsArgs(apb="a", limit=10, page=-1)


def test_conversation_messages_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        ConversationMessagesArgs(apb="", customer_account_id="c")
    with pytest.raises(ValueError, match="customer_account_id must not be empty"):
        ConversationMessagesArgs(apb="a", customer_account_id="")


def test_baskets_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        BasketsArgs(apb="", patient_id="p")
    with pytest.raises(ValueError, match="patient_id must not be empty"):
        BasketsArgs(apb="a", patient_id="")
    with pytest.raises(ValueError, match="skip must not be negative"):
        BasketsArgs(apb="a", patient_id="p", skip=-1, take=10)
    with pytest.raises(ValueError, match="take must be positive"):
        BasketsArgs(apb="a", patient_id="p", skip=0, take=0)


def test_draft_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        DraftArgs(apb="", account_id="a")
    with pytest.raises(ValueError, match="account_id must not be empty"):
        DraftArgs(apb="a", account_id="")


def test_draft_product_validation() -> None:
    with pytest.raises(ValueError, match="product_cnk must not be empty"):
        DraftProduct(product_cnk="", quantity=1)
    with pytest.raises(ValueError, match="quantity must be positive"):
        DraftProduct(product_cnk="1", quantity=0)


def test_draft_write_args_validation() -> None:
    with pytest.raises(ValueError, match="patient_id must not be empty"):
        DraftWriteArgs(apb="a", account_id="c", patient_id="")
    with pytest.raises(ValueError, match="account_id must not be empty"):
        DraftWriteArgs(apb="a", account_id="", patient_id="p")
    with pytest.raises(ValueError, match="apb must not be empty"):
        DraftWriteArgs(apb="", account_id="c", patient_id="p")


def test_draft_update_args_validation() -> None:
    with pytest.raises(ValueError, match="basket_id must not be empty"):
        DraftUpdateArgs(apb="a", account_id="c", patient_id="p", basket_id="")
    with pytest.raises(ValueError, match="patient_id must not be empty"):
        DraftUpdateArgs(apb="a", account_id="c", patient_id="", basket_id="b")


def test_submit_basket_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        SubmitBasketArgs(apb="", basket_id="b", patient_id="p")
    with pytest.raises(ValueError, match="basket_id must not be empty"):
        SubmitBasketArgs(apb="a", basket_id="", patient_id="p")
    with pytest.raises(ValueError, match="patient_id must not be empty"):
        SubmitBasketArgs(apb="a", basket_id="b", patient_id="")


def test_basket_id_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        BasketIdArgs(apb="", basket_id="b")
    with pytest.raises(ValueError, match="basket_id must not be empty"):
        BasketIdArgs(apb="a", basket_id="")


def test_self_onboarding_args_validation() -> None:
    with pytest.raises(ValueError, match="account_id must not be empty"):
        SelfOnboardingArgs(account_id="", apb="a")
    with pytest.raises(ValueError, match="apb must not be empty"):
        SelfOnboardingArgs(account_id="c", apb="")


def test_product_in_apb_args_validation() -> None:
    with pytest.raises(ValueError, match="cnk must not be empty"):
        ProductInApbArgs(cnk="", apb="a")
    with pytest.raises(ValueError, match="apb must not be empty"):
        ProductInApbArgs(cnk="1234567", apb="")


def test_product_in_apb_by_gtin_args_validation() -> None:
    with pytest.raises(ValueError, match="gtin must not be empty"):
        ProductInApbByGtinArgs(gtin="", apb="a")
    with pytest.raises(ValueError, match="apb must not be empty"):
        ProductInApbByGtinArgs(gtin="03585552783337", apb="")


def test_search_products_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        SearchProductsArgs(apb="", query="paracetamol")
    with pytest.raises(ValueError, match="query must not be empty"):
        SearchProductsArgs(apb="a", query="")
    with pytest.raises(ValueError, match="limit and page must be positive"):
        SearchProductsArgs(apb="a", query="paracetamol", limit=0)
    with pytest.raises(ValueError, match="limit and page must be positive"):
        SearchProductsArgs(apb="a", query="paracetamol", page=0)


def test_scheme_product_args_validation() -> None:
    with pytest.raises(ValueError, match="patient_id must not be empty"):
        SchemeProductArgs(apb="a", cnk="1234567", patient_id="")
    with pytest.raises(ValueError, match="apb must not be empty"):
        SchemeProductArgs(apb="", cnk="1234567", patient_id="p")
    with pytest.raises(ValueError, match="cnk must not be empty"):
        SchemeProductArgs(apb="a", cnk="", patient_id="p")


def test_pay_basket_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        PayBasketArgs(apb="", basket_id="b", redirect_url="https://x/")
    with pytest.raises(ValueError, match="basket_id must not be empty"):
        PayBasketArgs(apb="a", basket_id="", redirect_url="https://x/")
    with pytest.raises(ValueError, match="redirect_url must not be empty"):
        PayBasketArgs(apb="a", basket_id="b", redirect_url="")


def test_kava_product_args_validation() -> None:
    with pytest.raises(ValueError, match="cnk must not be empty"):
        KavaProductArgs(cnk="")


def test_message_draft_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        MessageDraftArgs(apb="", account_id="a")
    with pytest.raises(ValueError, match="account_id must not be empty"):
        MessageDraftArgs(apb="a", account_id="")


def test_message_draft_id_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        MessageDraftIdArgs(apb="", account_id="c", draft_id="d")
    with pytest.raises(ValueError, match="account_id must not be empty"):
        MessageDraftIdArgs(apb="a", account_id="", draft_id="d")
    with pytest.raises(ValueError, match="draft_id must not be empty"):
        MessageDraftIdArgs(apb="a", account_id="c", draft_id="")


def test_message_attachment_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        MessageAttachmentUploadArgs(
            apb="", account_id="c", draft_id="d", filename="f", content=b"x"
        )
    with pytest.raises(ValueError, match="account_id must not be empty"):
        MessageAttachmentUploadArgs(
            apb="a", account_id="", draft_id="d", filename="f", content=b"x"
        )
    with pytest.raises(ValueError, match="draft_id must not be empty"):
        MessageAttachmentUploadArgs(
            apb="a", account_id="c", draft_id="", filename="f", content=b"x"
        )
    with pytest.raises(ValueError, match="filename must not be empty"):
        MessageAttachmentUploadArgs(
            apb="a", account_id="c", draft_id="d", filename="", content=b"x"
        )
    custom = MessageAttachmentUploadArgs(
        apb="a",
        account_id="c",
        draft_id="d",
        filename="f.pdf",
        content=b"x",
        content_type="application/octet-stream",
    )
    assert MESSAGE_ATTACHMENT_UPLOAD.form_body is not None
    custom_form = MESSAGE_ATTACHMENT_UPLOAD.form_body(custom)
    assert custom_form._fields[0][1]["Content-Type"] == "application/octet-stream"
    with pytest.raises(ValueError, match="apb must not be empty"):
        MessageAttachmentDeleteArgs(apb="", account_id="c", attachment_id="e")
    with pytest.raises(ValueError, match="account_id must not be empty"):
        MessageAttachmentDeleteArgs(apb="a", account_id="", attachment_id="e")
    with pytest.raises(ValueError, match="attachment_id must not be empty"):
        MessageAttachmentDeleteArgs(apb="a", account_id="c", attachment_id="")


def test_message_mark_read_args_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        MessageMarkReadArgs(apb="", account_id="c", message_id="m")
    with pytest.raises(ValueError, match="account_id must not be empty"):
        MessageMarkReadArgs(apb="a", account_id="", message_id="m")
    with pytest.raises(ValueError, match="message_id must not be empty"):
        MessageMarkReadArgs(apb="a", account_id="c", message_id="")


def test_optional_attachment_id_rejects_unusable_payloads() -> None:
    assert _optional_attachment_id(None) is None
    assert _optional_attachment_id("junk") is None
    assert _optional_attachment_id({}) is None
    assert _optional_attachment_id({"attachmentId": 3}) is None
    assert _optional_attachment_id({"attachmentId": "a"}) == "a"


def test_lookups_mark_not_found_as_none() -> None:
    for endpoint in (DRAFT_BASKET, PRODUCT_IN_APB, PRODUCT_IN_APB_BY_GTIN, MESSAGE_DRAFT):
        assert endpoint.not_found_is_none is True
    for other in (
        ACCOUNT,
        ORGANIZATION,
        PATIENT,
        PHARMACY_PREFERENCES,
        SCHEME_DAY,
        SCHEME_NONDAILY,
        SCHEME_PRODUCT,
        SEARCH_PRODUCTS,
        KAVA_PRODUCT,
        MESSAGE_DRAFT_SAVE,
        MESSAGE_DRAFT_UPDATE,
        MESSAGE_DRAFT_SEND,
        MESSAGE_ATTACHMENT_UPLOAD,
        MESSAGE_ATTACHMENT_DELETE,
        MESSAGE_MARK_READ,
        SERVICE_MESSAGES,
        TECHNICAL_INTERRUPTIONS,
        PAY_BASKET,
        CONVERSATIONS,
        CONVERSATION_MESSAGES,
        BASKETS,
        DRAFT_SAVE,
        DRAFT_UPDATE,
        DRAFT_CLEAR,
        SUBMIT_BASKET,
        CANCEL_BASKET,
        SELF_ONBOARDING,
    ):
        assert other.not_found_is_none is False


def test_product_lookups_target_the_catalog_host() -> None:
    args = ProductInApbArgs(cnk="1234567", apb="a")
    gtin_args = ProductInApbByGtinArgs(gtin="03585552783337", apb="a")
    assert PRODUCT_IN_APB.base_url == "https://api.catalog.procura.farmad.be"
    assert PRODUCT_IN_APB.url(args) == "/api/catalog/products/1234567/a"
    assert PRODUCT_IN_APB_BY_GTIN.base_url == "https://api.catalog.procura.farmad.be"
    assert PRODUCT_IN_APB_BY_GTIN.url(gtin_args) == "/api/catalog/products/gtin/03585552783337/a"


def test_search_products_targets_the_catalog_host() -> None:
    assert SEARCH_PRODUCTS.base_url == "https://api.catalog.procura.farmad.be"
    assert SEARCH_PRODUCTS.url(SearchProductsArgs(apb="a", query="paracetamol")) == (
        "/api/catalog/products"
    )


def test_search_products_params_render_the_query() -> None:
    args = SearchProductsArgs(apb="a", query="paracetamol", limit=3, page=2)
    assert SEARCH_PRODUCTS.params(args) == {
        "SearchTerm": "paracetamol",
        "Apb": "a",
        "Page": "2",
        "Limit": "3",
        "Language": "nl",
    }


def test_scheme_product_params_render_the_language() -> None:
    args = SchemeProductArgs(apb="a", cnk="1234567", patient_id="p", language="fr")
    assert SCHEME_PRODUCT.params(args) == {"language": "fr"}
    assert SCHEME_PRODUCT.url(args) == (
        "/medicationscheme/api/medicationscheme/p/scheme/a/product/1234567"
    )


def test_pay_basket_renders_the_body() -> None:
    args = PayBasketArgs(apb="a", basket_id="b", redirect_url="https://x/")
    assert PAY_BASKET.url(args) == "/customerbasket/api/a/customerbaskets/b/pay"
    assert PAY_BASKET.json_body is not None
    assert PAY_BASKET.json_body(args) == {"redirectUrl": "https://x/"}


def test_kava_product_targets_the_catalog_host() -> None:
    assert KAVA_PRODUCT.base_url == "https://api.catalog.procura.farmad.be"
    assert KAVA_PRODUCT.url(KavaProductArgs(cnk="1234567")) == "/api/catalog/products/kava/1234567"


def test_message_draft_endpoints_render_their_paths() -> None:
    draft_args = MessageDraftArgs(apb="a", account_id="c")
    assert MESSAGE_DRAFT.url(draft_args) == "/messaging/api/draft/a/c"
    save_args = MessageDraftSaveArgs(apb="a", account_id="c", body="text")
    assert MESSAGE_DRAFT_SAVE.url(save_args) == "/messaging/api/draft/a/c"
    assert MESSAGE_DRAFT_SAVE.json_body is not None
    assert MESSAGE_DRAFT_SAVE.json_body(save_args) == {"body": "text", "reference": ""}
    update_args = MessageDraftUpdateArgs(apb="a", account_id="c", draft_id="d", body="text")
    assert MESSAGE_DRAFT_UPDATE.url(update_args) == "/messaging/api/draft/a/c/d"
    assert MESSAGE_DRAFT_UPDATE.json_body is not None
    assert MESSAGE_DRAFT_UPDATE.json_body(update_args) == {"body": "text", "reference": ""}
    send_args = MessageDraftIdArgs(apb="a", account_id="c", draft_id="d")
    assert MESSAGE_DRAFT_SEND.url(send_args) == "/messaging/api/draft/a/c/send/d"
    upload_args = MessageAttachmentUploadArgs(
        apb="a", account_id="c", draft_id="d", filename="note.pdf", content=b"data"
    )
    assert MESSAGE_ATTACHMENT_UPLOAD.url(upload_args) == "/messaging/api/draft/a/c/d/attachment"
    assert MESSAGE_ATTACHMENT_UPLOAD.form_body is not None
    form = MESSAGE_ATTACHMENT_UPLOAD.form_body(upload_args)
    assert len(form._fields) == 1
    assert form._fields[0][0]["name"] == "uploadedFile"
    assert form._fields[0][0]["filename"] == "note.pdf"
    assert form._fields[0][1]["Content-Type"] == "application/pdf"
    assert form._fields[0][2] == b"data"
    delete_args = MessageAttachmentDeleteArgs(apb="a", account_id="c", attachment_id="e")
    assert MESSAGE_ATTACHMENT_DELETE.url(delete_args) == "/messaging/api/draft/a/c/attachment/e"
    mark_read_args = MessageMarkReadArgs(apb="a", account_id="c", message_id="m")
    assert MESSAGE_MARK_READ.url(mark_read_args) == "/messaging/api/message/a/c/m"


def test_platform_endpoints_render_their_paths() -> None:
    assert SERVICE_MESSAGES.url(PlatformArgs()) == "/notifications/api/servicemessages"
    assert SERVICE_MESSAGES.version == "2.1"
    assert TECHNICAL_INTERRUPTIONS.url(PlatformArgs()) == (
        "/notifications/api/technicalinterruptions"
    )


def test_scheme_day_params_render_the_window() -> None:
    args = SchemeDayArgs(apb="a", patient_id="p", from_=START, until=END, language="nl")
    params = SCHEME_DAY.params(args)
    assert params == {
        "from": "2026-10-01T00:00:00.000Z",
        "until": "2026-10-07T00:00:00.000Z",
        "language": "nl",
    }


def test_scheme_nondaily_params_render_the_day() -> None:
    args = SchemeNondailyArgs(apb="a", patient_id="p", day=date(2026, 10, 1))
    params = SCHEME_NONDAILY.params(args)
    assert params == {"day": "2026-10-01T00:00:00.000Z", "language": "nl"}


def test_pagination_params_render() -> None:
    assert CONVERSATIONS.params(ConversationsArgs(apb="a", limit=5, page=2)) == {
        "Limit": "5",
        "Page": "2",
    }
    assert BASKETS.params(BasketsArgs(apb="a", patient_id="p", skip=3, take=7)) == {
        "PatientId": "p",
        "Skip": "3",
        "Take": "7",
    }


def test_draft_body_renders_products() -> None:
    products = (DraftProduct(product_cnk="1", quantity=2),)
    args = DraftWriteArgs(apb="a", account_id="c", patient_id="p", products=products)
    json_body = DRAFT_SAVE.json_body
    assert json_body is not None
    assert json_body(args) == {
        "patientId": "p",
        "products": [{"productCnk": "1", "quantityOrdered": 2, "patientId": "p"}],
    }


def test_submit_body_renders_the_order() -> None:
    products = (DraftProduct(product_cnk="1", quantity=1),)
    args = SubmitBasketArgs(
        apb="a",
        basket_id="b",
        patient_id="p",
        products=products,
        comment="hi",
        unit_prices=(("1", 2.5),),
        pay_online=False,
    )
    json_body = SUBMIT_BASKET.json_body
    assert json_body is not None
    assert json_body(args) == {
        "patientId": "p",
        "commentCustomer": "hi",
        "products": [{"productCnk": "1", "quantityOrdered": 1, "patientId": "p"}],
        "unitPrices": [{"productCnk": "1", "price": 2.5}],
        "preferPaymentAtPickup": True,
        "redirectUrl": None,
    }


def test_cancel_body_is_absent() -> None:
    args = BasketIdArgs(apb="a", basket_id="b")
    assert CANCEL_BASKET.json_body is None
    assert CANCEL_BASKET.params(args) == {}


def test_optional_id_and_messages_parse_helpers() -> None:
    assert _optional_id("plain") == "plain"
    assert _optional_id({"id": "x"}) == "x"
    assert _optional_id({"id": 5}) is None
    assert _optional_id(["nope"]) is None
    assert _parse_messages([{"id": "m"}, "junk"]) is not None
    assert _parse_messages({"id": "m"}) == ()


def test_conversation_messages_args_limit_and_page_validation() -> None:
    with pytest.raises(ValueError, match="limit must be positive"):
        ConversationMessagesArgs(apb="a", customer_account_id="c", limit=0)
    with pytest.raises(ValueError, match="page must not be negative"):
        ConversationMessagesArgs(apb="a", customer_account_id="c", page=-1)


def test_draft_update_args_apb_and_account_validation() -> None:
    with pytest.raises(ValueError, match="apb must not be empty"):
        DraftUpdateArgs(apb="", account_id="c", patient_id="p", basket_id="b")
    with pytest.raises(ValueError, match="account_id must not be empty"):
        DraftUpdateArgs(apb="a", account_id="", patient_id="p", basket_id="b")


def test_prescriptions_args_validation() -> None:
    with pytest.raises(ValueError, match="page must not be negative"):
        PrescriptionsArgs(page=-1)


def test_prescription_args_validation() -> None:
    with pytest.raises(ValueError, match="prescription_id must not be empty"):
        PrescriptionArgs(prescription_id="")
