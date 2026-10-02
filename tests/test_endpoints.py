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
    ORGANIZATION,
    PATIENT,
    PHARMACY_PREFERENCES,
    PRODUCT_IN_APB,
    PRODUCT_IN_APB_BY_GTIN,
    SCHEME_DAY,
    SCHEME_NONDAILY,
    SEARCH_PRODUCTS,
    SELF_ONBOARDING,
    SUBMIT_BASKET,
    BasketIdArgs,
    BasketsArgs,
    ConversationMessagesArgs,
    ConversationsArgs,
    DraftArgs,
    DraftUpdateArgs,
    DraftWriteArgs,
    PatientArgs,
    PharmacyArgs,
    PrescriptionArgs,
    PrescriptionsArgs,
    ProductInApbArgs,
    ProductInApbByGtinArgs,
    SchemeDayArgs,
    SchemeNondailyArgs,
    SearchProductsArgs,
    SelfOnboardingArgs,
    SubmitBasketArgs,
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


def test_lookups_mark_not_found_as_none() -> None:
    for endpoint in (DRAFT_BASKET, PRODUCT_IN_APB, PRODUCT_IN_APB_BY_GTIN):
        assert endpoint.not_found_is_none is True
    for other in (
        ACCOUNT,
        ORGANIZATION,
        PATIENT,
        PHARMACY_PREFERENCES,
        SCHEME_DAY,
        SCHEME_NONDAILY,
        SEARCH_PRODUCTS,
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
