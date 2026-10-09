"""Client tests: getters, defaults, retries, writes, and session ownership."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import aiohttp
import pytest
from aioresponses import aioresponses

if TYPE_CHECKING:
    from aioresponses.core import RequestCall
    from yarl import URL


from aiofarmad import (
    DraftProduct,
    FarmadAuthenticationError,
    FarmadAuthorizationError,
    FarmadClient,
    FarmadClientClosedError,
    FarmadCommunicationError,
    FarmadEhealthAuthorizationRequiredError,
    FarmadInvalidResponseError,
    FarmadNotFoundError,
)

from .conftest import (
    ACCOUNT_ID,
    APB,
    OTP,
    PASSWORD,
    PATIENT_ID,
    USERNAME,
    alb_url,
    catalog_url,
    ehealth_url,
    make_jwt,
    register_login_flow,
)

ACCESS = make_jwt()
REFRESH = "stored-refresh-token"


def first_request_key(
    log: dict[tuple[str, URL], list[RequestCall]], method: str, url_prefix: str
) -> tuple[str, URL]:
    """Find the recorded request key that starts with one URL."""
    for key in log:
        recorded_method, recorded_url = key
        if recorded_method == method and str(recorded_url).startswith(url_prefix):
            return recorded_method, recorded_url
    msg = f"no recorded request for {method} {url_prefix}"
    raise AssertionError(msg)


def make_client(session: aiohttp.ClientSession | None = None) -> FarmadClient:
    return FarmadClient(
        session,
        access_token=ACCESS,
        refresh_token=REFRESH,
    )


async def test_login_adopts_tokens() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            register_login_flow(m)
            client = FarmadClient(session, email=USERNAME, password=PASSWORD)
            tokens = await client.async_login()
    assert tokens.access_token == "new-access-token"
    assert tokens.refresh_token == "new-refresh-token"
    assert tokens.expires_in == 36000
    assert client.access_token == "new-access-token"
    assert client.refresh_token == "new-refresh-token"


async def test_mfa_login_awaits_the_otp_provider() -> None:
    calls: list[str] = []

    async def provider() -> str:
        calls.append("called")
        return OTP

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            register_login_flow(m, mfa=True)
            client = FarmadClient(session, email=USERNAME, password=PASSWORD, otp_provider=provider)
            tokens = await client.async_login()
    assert calls == ["called"]
    assert tokens.access_token == "new-access-token"
    assert client.access_token == "new-access-token"


async def test_login_requires_credentials() -> None:
    client = make_client()
    with pytest.raises(FarmadAuthenticationError, match="Credentials are required"):
        await client.async_login()
    await client.async_close()


async def test_client_with_owned_session_closes_it(
    created_sessions: list[aiohttp.ClientSession],
) -> None:
    client = FarmadClient(access_token=ACCESS, refresh_token=REFRESH)
    assert created_sessions
    assert not created_sessions[0].closed
    await client.async_close()
    assert created_sessions[0].closed


async def test_client_keeps_injected_session_open() -> None:
    async with aiohttp.ClientSession() as session:
        client = FarmadClient(session, access_token=ACCESS, refresh_token=REFRESH)
        await client.async_close()
        assert not session.closed


async def test_context_manager_closes_owned_session(
    created_sessions: list[aiohttp.ClientSession],
) -> None:
    async with FarmadClient(access_token=ACCESS, refresh_token=REFRESH):
        assert created_sessions
    assert created_sessions[0].closed


async def test_closed_client_rejects_calls() -> None:
    client = make_client()
    await client.async_close()
    with pytest.raises(FarmadClientClosedError):
        await client.async_get_account()


async def test_get_account(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}"),
                payload=load_fixture("account.json"),
            )
            account = await make_client(session).async_get_account()
    assert account.id == ACCOUNT_ID
    assert account.entitled_pharmacies == ("343602",)


async def test_get_account_with_explicit_id(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url("/usermanagement/api/account/other-id"),
                payload=load_fixture("account.json"),
            )
            account = await make_client(session).async_get_account("other-id")
    assert account.id == ACCOUNT_ID


async def test_get_account_without_any_id_raises() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}"), payload={})
            client = FarmadClient(
                session,
                access_token=make_jwt(account_id=""),
                refresh_token=REFRESH,
            )
            with pytest.raises(FarmadAuthenticationError, match="account_id is required"):
                await client.async_get_account()


async def test_claims_default_account_and_patient() -> None:
    client = FarmadClient(access_token=make_jwt(), refresh_token=REFRESH)
    assert client.account_id == ACCOUNT_ID
    assert client.patient_id == PATIENT_ID
    await client.async_close()


async def test_get_organization(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(f"/usermanagement/api/organization/{APB}"),
                payload=load_fixture("organization.json"),
            )
            pharmacy = await make_client(session).async_get_organization(APB)
    assert pharmacy.name == "Apotheek Voorbeeld"


async def test_get_patient(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(f"/patientmanagement/api/patients/{PATIENT_ID}"),
                payload=load_fixture("patient.json"),
            )
            patient = await make_client(session).async_get_patient()
    assert patient.patient_id == PATIENT_ID
    assert len(patient.pharmacies) == 8


async def test_get_pharmacy_preferences(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(f"/customerbasket/api/{APB}/pharmacypreferences/for-customer"),
                payload=load_fixture("pharmacy_preferences.json"),
            )
            preferences = await make_client(session).async_get_pharmacy_preferences(APB)
    assert preferences.allow_online_payments is False


async def test_get_medication_day_scheme_sends_window(load_fixture: Callable[[str], Any]) -> None:
    start = datetime(2026, 10, 1, tzinfo=UTC)
    end = datetime(2026, 10, 7, 23, 59, 59, 999000, tzinfo=UTC)
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(f"/medicationscheme/api/medicationscheme/{PATIENT_ID}/scheme/{APB}/day"),
                payload=load_fixture("scheme_day.json"),
            )
            scheme = await make_client(session).async_get_medication_day_scheme(
                APB, from_=start, until=end
            )
    assert len(scheme) == 2
    request_log = m.requests
    key = first_request_key(
        request_log,
        "GET",
        f"https://alb-prod.procura.farmad.be/medicationscheme/api/medicationscheme/{PATIENT_ID}/scheme/{APB}/day",
    )
    query = request_log[key][0].kwargs["params"]
    assert query["api-version"] == "2.5"
    assert query["from"] == "2026-10-01T00:00:00.000Z"
    assert query["until"] == "2026-10-07T23:59:59.999Z"
    assert query["language"] == "nl"


async def test_get_medication_nondaily_products(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(
                    f"/medicationscheme/api/medicationscheme/{PATIENT_ID}/scheme/{APB}/nondaily"
                ),
                payload=load_fixture("scheme_nondaily.json"),
            )
            products = await make_client(session).async_get_medication_nondaily_products(
                APB, day=date(2026, 10, 1)
            )
    assert len(products) == 2


async def test_get_conversations(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(f"/messaging/api/message/{APB}"),
                payload=load_fixture("conversations.json"),
            )
            conversations = await make_client(session).async_get_conversations(APB)
    assert len(conversations) == 2
    request_log = m.requests
    key = first_request_key(
        request_log, "GET", f"https://alb-prod.procura.farmad.be/messaging/api/message/{APB}"
    )
    assert request_log[key][0].kwargs["params"]["api-version"] == "4.0"


async def test_get_conversation_messages(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(f"/messaging/api/message/{APB}/{ACCOUNT_ID}"),
                payload=load_fixture("messages.json"),
            )
            messages = await make_client(session).async_get_conversation_messages(APB, ACCOUNT_ID)
    assert len(messages) == 2


async def test_get_baskets(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(f"/customerbasket/api/{APB}/customerbaskets"),
                payload=load_fixture("baskets.json"),
            )
            baskets = await make_client(session).async_get_baskets(APB)
    assert len(baskets) == 1
    assert baskets[0].comment_pharmacy is not None


async def test_get_draft_basket(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(f"/customerbasket/api/{APB}/drafts/{ACCOUNT_ID}"),
                payload=load_fixture("draft_basket.json"),
            )
            draft = await make_client(session).async_get_draft_basket(APB)
    assert draft is not None
    assert draft.id == "draft-1"


async def test_get_draft_basket_without_draft_is_none() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url(f"/customerbasket/api/{APB}/drafts/{ACCOUNT_ID}"), status=404, payload={})
            draft = await make_client(session).async_get_draft_basket(APB)
    assert draft is None


async def test_save_draft_basket_posts_body() -> None:
    products = (DraftProduct(product_cnk="1122334", quantity=2),)
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                alb_url(f"/customerbasket/api/{APB}/drafts/{ACCOUNT_ID}"), payload={"id": "draft-9"}
            )
            draft_id = await make_client(session).async_save_draft_basket(APB, products=products)
    assert draft_id == "draft-9"
    request_log = m.requests
    key = first_request_key(
        request_log,
        "POST",
        f"https://alb-prod.procura.farmad.be/customerbasket/api/{APB}/drafts/{ACCOUNT_ID}",
    )
    body = request_log[key][0].kwargs["json"]
    assert body == {
        "patientId": PATIENT_ID,
        "products": [{"productCnk": "1122334", "quantityOrdered": 2, "patientId": PATIENT_ID}],
    }


async def test_update_draft_basket_patches_body() -> None:
    products = (DraftProduct(product_cnk="1122334", quantity=1),)
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.patch(
                alb_url(f"/customerbasket/api/{APB}/drafts/{ACCOUNT_ID}/draft-9"),
                payload={"id": "draft-9"},
            )
            draft_id = await make_client(session).async_update_draft_basket(
                APB, "draft-9", products=products
            )
    assert draft_id == "draft-9"


async def test_clear_draft_basket() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.delete(alb_url(f"/customerbasket/api/{APB}/drafts/{ACCOUNT_ID}"), status=200, body="")
            await make_client(session).async_clear_draft_basket(APB)


async def test_submit_basket_sends_order_body() -> None:
    products = (DraftProduct(product_cnk="1122334", quantity=1),)
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.patch(
                alb_url(f"/customerbasket/api/{APB}/customerbaskets/draft-9/submit"),
                payload={"id": "basket-9"},
            )
            basket_id = await make_client(session).async_submit_basket(
                APB,
                "draft-9",
                products=products,
                comment="repeat order",
                unit_prices=(("1122334", 4.95),),
                pay_online=True,
            )
    assert basket_id == "basket-9"
    request_log = m.requests
    key = first_request_key(
        request_log,
        "PATCH",
        f"https://alb-prod.procura.farmad.be/customerbasket/api/{APB}/customerbaskets/draft-9/submit",
    )
    body = request_log[key][0].kwargs["json"]
    assert body["commentCustomer"] == "repeat order"
    assert body["preferPaymentAtPickup"] is False
    assert body["unitPrices"] == [{"productCnk": "1122334", "price": 4.95}]


async def test_cancel_basket() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.put(
                alb_url(f"/customerbasket/api/{APB}/customerbaskets/basket-9/cancel"),
                status=200,
                body="",
            )
            await make_client(session).async_cancel_basket(APB, "basket-9")


async def test_get_product_in_apb(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                catalog_url(f"/api/catalog/products/3093242/{APB}"),
                payload=load_fixture("product_in_apb.json"),
            )
            product = await make_client(session).async_get_product_in_apb(APB, "3093242")
    assert product is not None
    assert product.cnk == "3093242"
    assert product.descriptions["nl"] == "FEBELCARE MED1 STERIELE GAASKOMPRES 5,0X5,0CM 40X1"
    assert product.brand == "Febelcare"
    assert product.price is not None
    assert product.price.sales_price == 3.1
    request_log = m.requests
    key = first_request_key(
        request_log,
        "GET",
        f"https://api.catalog.procura.farmad.be/api/catalog/products/3093242/{APB}",
    )
    assert request_log[key][0].kwargs["params"]["api-version"] == "5.3"


async def test_get_product_in_apb_by_gtin(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                catalog_url(f"/api/catalog/products/gtin/03585552783337/{APB}"),
                payload=load_fixture("product_in_apb_by_gtin.json"),
            )
            product = await make_client(session).async_get_product_in_apb_by_gtin(
                APB, "03585552783337"
            )
    assert product is not None
    assert product.cnk == "1799121"
    assert product.stock is not None
    assert product.stock.availability == "Pharmacy"
    assert product.product_codes[0].code_type == "Gtin"


async def test_get_product_in_apb_not_found_is_none() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                catalog_url(f"/api/catalog/products/0000000/{APB}"),
                status=404,
                payload={},
            )
            product = await make_client(session).async_get_product_in_apb(APB, "0000000")
    assert product is None


async def test_get_product_in_apb_empty_answer_is_none() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                catalog_url(f"/api/catalog/products/gtin/0000000000000/{APB}"),
                status=204,
                body="",
            )
            product = await make_client(session).async_get_product_in_apb_by_gtin(
                APB, "0000000000000"
            )
    assert product is None


async def test_get_product_in_apb_requires_a_role() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                catalog_url(f"/api/catalog/products/3093242/{APB}"),
                status=403,
                payload={},
            )
            with pytest.raises(FarmadAuthorizationError):
                await make_client(session).async_get_product_in_apb(APB, "3093242")


async def test_search_products_in_apb(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                catalog_url("/api/catalog/products"),
                payload=load_fixture("products_search.json"),
            )
            products = await make_client(session).async_search_products_in_apb(APB, "paracetamol")
    assert len(products) == 3
    assert products[0].cnk == "2810901"
    assert products[0].brand == "Teva"
    assert products[2].cnk == "2881100"
    request_log = m.requests
    key = first_request_key(
        request_log,
        "GET",
        "https://api.catalog.procura.farmad.be/api/catalog/products",
    )
    params = request_log[key][0].kwargs["params"]
    assert params["api-version"] == "5.3"
    assert params["SearchTerm"] == "paracetamol"
    assert params["Apb"] == APB
    assert params["Page"] == "1"
    assert params["Limit"] == "25"
    assert params["Language"] == "nl"


async def test_search_products_in_apb_passes_the_page() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(catalog_url("/api/catalog/products"), payload={"hits": []})
            await make_client(session).async_search_products_in_apb(
                APB, "paracetamol", limit=3, page=2, language="fr"
            )
    request_log = m.requests
    key = first_request_key(
        request_log,
        "GET",
        "https://api.catalog.procura.farmad.be/api/catalog/products",
    )
    params = request_log[key][0].kwargs["params"]
    assert params["Page"] == "2"
    assert params["Limit"] == "3"
    assert params["Language"] == "fr"


async def test_search_products_in_apb_without_matches_is_empty() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                catalog_url("/api/catalog/products"),
                payload={"hits": [], "aggregates": []},
            )
            products = await make_client(session).async_search_products_in_apb(APB, "zzzzqqq")
    assert products == ()


async def test_search_products_in_apb_requires_a_role() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                catalog_url("/api/catalog/products"),
                status=403,
                payload={},
            )
            with pytest.raises(FarmadAuthorizationError):
                await make_client(session).async_search_products_in_apb(APB, "paracetamol")


async def test_get_kava_product(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                catalog_url("/api/catalog/products/kava/2810901"),
                payload=load_fixture("kava_product.json"),
            )
            kava = await make_client(session).async_get_kava_product("2810901")
    assert kava.cnk == "2810901"
    assert kava.is_subject_to_repayment is True
    assert kava.is_fmd_product is True
    assert kava.patient_information_urls["nl"].startswith("https://app.fagg-afmps.be/")
    request_log = m.requests
    key = first_request_key(
        request_log,
        "GET",
        "https://api.catalog.procura.farmad.be/api/catalog/products/kava/2810901",
    )
    assert request_log[key][0].kwargs["params"]["api-version"] == "5.3"


async def test_get_medication_scheme_for_product(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(
                    f"/medicationscheme/api/medicationscheme/{PATIENT_ID}/scheme/{APB}"
                    "/product/2810901"
                ),
                payload=load_fixture("scheme_product.json"),
            )
            entries = await make_client(session).async_get_medication_scheme_for_product(
                APB, "2810901"
            )
    assert entries == ()
    request_log = m.requests
    key = first_request_key(
        request_log,
        "GET",
        f"https://alb-prod.procura.farmad.be/medicationscheme/api/medicationscheme/{PATIENT_ID}"
        f"/scheme/{APB}/product/2810901",
    )
    params = request_log[key][0].kwargs["params"]
    assert params["api-version"] == "2.5"
    assert params["language"] == "nl"


async def test_get_message_draft(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url(f"/messaging/api/draft/{APB}/{ACCOUNT_ID}"),
                payload=load_fixture("message_draft.json"),
            )
            draft = await make_client(session).async_get_message_draft(APB)
    assert draft is not None
    assert draft.id
    assert len(draft.attachments) == 5


async def test_get_message_draft_without_one_is_none() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url(f"/messaging/api/draft/{APB}/{ACCOUNT_ID}"), status=204, body="")
            draft = await make_client(session).async_get_message_draft(APB)
    assert draft is None


async def test_save_message_draft(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                alb_url(f"/messaging/api/draft/{APB}/{ACCOUNT_ID}"),
                payload=load_fixture("message_draft.json"),
            )
            draft = await make_client(session).async_save_message_draft(APB, "hello")
    assert draft is not None
    request_log = m.requests
    key = first_request_key(
        request_log,
        "POST",
        f"https://alb-prod.procura.farmad.be/messaging/api/draft/{APB}/{ACCOUNT_ID}",
    )
    assert request_log[key][0].kwargs["json"] == {"body": "hello", "reference": ""}
    assert request_log[key][0].kwargs["params"]["api-version"] == "4.0"


async def test_update_message_draft() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.put(alb_url(f"/messaging/api/draft/{APB}/{ACCOUNT_ID}/draft-1"), status=200, body="")
            await make_client(session).async_update_message_draft(APB, "draft-1", "new text")
    request_log = m.requests
    key = first_request_key(
        request_log,
        "PUT",
        f"https://alb-prod.procura.farmad.be/messaging/api/draft/{APB}/{ACCOUNT_ID}/draft-1",
    )
    assert request_log[key][0].kwargs["json"] == {"body": "new text", "reference": ""}


async def test_send_message_draft() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                alb_url(f"/messaging/api/draft/{APB}/{ACCOUNT_ID}/send/draft-1"),
                status=201,
                body="",
            )
            await make_client(session).async_send_message_draft(APB, "draft-1")
    request_log = m.requests
    key = first_request_key(
        request_log,
        "POST",
        f"https://alb-prod.procura.farmad.be/messaging/api/draft/{APB}/{ACCOUNT_ID}/send/draft-1",
    )
    assert request_log[key][0].kwargs["params"]["api-version"] == "4.0"


async def test_upload_message_attachment() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                alb_url(f"/messaging/api/draft/{APB}/{ACCOUNT_ID}/draft-1/attachment"),
                payload={
                    "attachmentId": "att-9",
                    "progressId": "00000000-0000-0000-0000-000000000000",
                },
            )
            attachment_id = await make_client(session).async_upload_message_attachment(
                APB, "draft-1", "note.pdf", b"hello"
            )
    assert attachment_id == "att-9"
    request_log = m.requests
    key = first_request_key(
        request_log,
        "POST",
        f"https://alb-prod.procura.farmad.be/messaging/api/draft/{APB}/{ACCOUNT_ID}"
        "/draft-1/attachment",
    )
    form = request_log[key][0].kwargs["data"]
    assert isinstance(form, aiohttp.FormData)
    assert len(form._fields) == 1
    assert form._fields[0][0]["name"] == "uploadedFile"
    assert form._fields[0][0]["filename"] == "note.pdf"
    assert form._fields[0][1]["Content-Type"] == "application/pdf"
    assert form._fields[0][2] == b"hello"


async def test_delete_message_attachment() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.delete(
                alb_url(f"/messaging/api/draft/{APB}/{ACCOUNT_ID}/attachment/att-1"),
                status=200,
                body="",
            )
            await make_client(session).async_delete_message_attachment(APB, "att-1")
    request_log = m.requests
    first_request_key(
        request_log,
        "DELETE",
        f"https://alb-prod.procura.farmad.be/messaging/api/draft/{APB}/{ACCOUNT_ID}"
        "/attachment/att-1",
    )


async def test_mark_message_as_read() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.put(
                alb_url(f"/messaging/api/message/{APB}/{ACCOUNT_ID}/msg-1"),
                status=200,
                body="",
            )
            await make_client(session).async_mark_message_as_read(APB, "msg-1")
    request_log = m.requests
    first_request_key(
        request_log,
        "PUT",
        f"https://alb-prod.procura.farmad.be/messaging/api/message/{APB}/{ACCOUNT_ID}/msg-1",
    )


async def test_get_service_messages(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url("/notifications/api/servicemessages"),
                payload=load_fixture("service_messages.json"),
            )
            messages = await make_client(session).async_get_service_messages()
    assert messages == ()
    request_log = m.requests
    key = first_request_key(
        request_log,
        "GET",
        "https://alb-prod.procura.farmad.be/notifications/api/servicemessages",
    )
    assert request_log[key][0].kwargs["params"]["api-version"] == "2.1"


async def test_has_technical_interruptions() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url("/notifications/api/technicalinterruptions"), payload=True)
            interrupted = await make_client(session).async_has_technical_interruptions()
    assert interrupted is True


async def test_has_no_technical_interruptions(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                alb_url("/notifications/api/technicalinterruptions"),
                payload=load_fixture("technical_interruptions.json"),
            )
            interrupted = await make_client(session).async_has_technical_interruptions()
    assert interrupted is False


async def test_pay_basket() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                alb_url(f"/customerbasket/api/{APB}/customerbaskets/basket-9/pay"),
                payload={"checkoutUrl": "https://pay.example/x"},
            )
            payment = await make_client(session).async_pay_basket(
                APB, "basket-9", "https://procura.farmad.be/auth-callback.html"
            )
    assert payment is not None
    assert payment.raw == {"checkoutUrl": "https://pay.example/x"}
    request_log = m.requests
    key = first_request_key(
        request_log,
        "POST",
        f"https://alb-prod.procura.farmad.be/customerbasket/api/{APB}/customerbaskets/basket-9/pay",
    )
    assert request_log[key][0].kwargs["json"] == {
        "redirectUrl": "https://procura.farmad.be/auth-callback.html"
    }


async def test_pay_basket_denied_answers_400() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                alb_url(f"/customerbasket/api/{APB}/customerbaskets/basket-9/pay"),
                status=400,
                payload={},
            )
            with pytest.raises(FarmadCommunicationError):
                await make_client(session).async_pay_basket(APB, "basket-9", "https://x/")


async def test_link_pharmacy_posts_apb() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}/self-onboarding"), body="")
            linked = await make_client(session).async_link_pharmacy("344107")
    assert linked is True
    request_log = m.requests
    key = first_request_key(
        request_log,
        "POST",
        f"https://alb-prod.procura.farmad.be/usermanagement/api/account/{ACCOUNT_ID}/self-onboarding",
    )
    assert request_log[key][0].kwargs["json"] == {"apb": "344107"}


async def test_authorization_error_surfaces() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url(f"/messaging/api/message/{APB}"), status=403, payload={})
            with pytest.raises(FarmadAuthorizationError):
                await make_client(session).async_get_conversations(APB)


async def test_not_found_error_surfaces() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url(f"/usermanagement/api/organization/{APB}"), status=404, payload={})
            with pytest.raises(FarmadNotFoundError):
                await make_client(session).async_get_organization(APB)


async def test_server_error_surfaces() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url(f"/usermanagement/api/organization/{APB}"), status=500, payload={})
            with pytest.raises(FarmadCommunicationError):
                await make_client(session).async_get_organization(APB)


async def test_stale_token_refreshes_and_retries_once(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}"), status=401, payload={})
            m.get(
                alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}"),
                payload=load_fixture("account.json"),
            )
            m.post(
                "https://signin.procura.farmad.be/oauth/token",
                payload={"access_token": "fresh-access", "refresh_token": "fresh-refresh"},
            )
            client = FarmadClient(
                session,
                access_token=make_jwt(),
                refresh_token=REFRESH,
            )
            account = await client.async_get_account()
    assert account.id == ACCOUNT_ID
    assert client.access_token == "fresh-access"


async def test_stale_token_without_refresh_token_raises() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}"), status=401, payload={})
            client = FarmadClient(session, access_token=make_jwt(exp_offset=-100.0))
            with pytest.raises(FarmadAuthenticationError):
                await client.async_get_account()


async def test_second_401_raises() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}"), status=401, payload={})
            m.get(alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}"), status=401, payload={})
            m.post(
                "https://signin.procura.farmad.be/oauth/token",
                payload={"access_token": "fresh-access", "refresh_token": "fresh-refresh"},
            )
            client = FarmadClient(
                session,
                access_token=make_jwt(),
                refresh_token=REFRESH,
            )
            with pytest.raises(FarmadAuthenticationError):
                await client.async_get_account()


async def test_on_token_refresh_receives_rotations() -> None:
    seen: list[tuple[str, str | None]] = []

    async def on_rotation(access_token: str, refresh_token: str | None) -> None:
        seen.append((access_token, refresh_token))

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}"), status=401, payload={})
            m.get(alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}"), payload={"id": ACCOUNT_ID})
            m.post(
                "https://signin.procura.farmad.be/oauth/token",
                payload={"access_token": "fresh-access", "refresh_token": "fresh-refresh"},
            )
            client = FarmadClient(
                session,
                access_token=make_jwt(),
                refresh_token=REFRESH,
                on_token_refresh=on_rotation,
            )
            await client.async_get_account()
    assert seen == [("fresh-access", "fresh-refresh")]


async def test_token_properties_expose_the_lifecycle() -> None:
    client = FarmadClient(access_token=ACCESS, refresh_token=REFRESH)
    assert client.access_token == ACCESS
    assert client.refresh_token == REFRESH
    await client.async_close()


async def test_get_prescriptions_sends_ehealth_cookie(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                ehealth_url("/ehealth/api/prescriptions"),
                payload=load_fixture("prescriptions.json"),
            )
            client = FarmadClient(
                session,
                access_token=ACCESS,
                refresh_token=REFRESH,
                ehealth_cookie=".AspNetCore.Cookies=abc123",
            )
            prescriptions = await client.async_get_prescriptions()
    assert len(prescriptions) == 2
    request_log = m.requests
    key = first_request_key(
        request_log, "GET", "https://procura.farmad.be/ehealth/api/prescriptions"
    )
    headers = request_log[key][0].kwargs["headers"]
    assert headers["Cookie"] == ".AspNetCore.Cookies=abc123"


async def test_get_prescriptions_without_cookie_still_calls() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(ehealth_url("/ehealth/api/prescriptions"), payload=[])
            client = FarmadClient(session, access_token=ACCESS, refresh_token=REFRESH)
            prescriptions = await client.async_get_prescriptions()
    assert prescriptions == ()


async def test_get_prescription_by_id(load_fixture: Callable[[str], Any]) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                ehealth_url("/ehealth/api/prescriptions/BEP10S18PLM4"),
                payload=load_fixture("prescription.json"),
            )
            client = FarmadClient(session, access_token=ACCESS, refresh_token=REFRESH)
            prescription = await client.async_get_prescription("BEP10S18PLM4")
    assert prescription is not None
    assert prescription.prescription_id == "BEP10S18PLM4"


async def test_ehealth_401_raises_consent_error() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(ehealth_url("/ehealth/api/prescriptions"), status=401, payload={})
            client = FarmadClient(session, access_token=ACCESS, refresh_token=REFRESH)
            with pytest.raises(FarmadEhealthAuthorizationRequiredError, match="eHealth session"):
                await client.async_get_prescriptions()


async def test_ehealth_401_does_not_burn_a_refresh() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(ehealth_url("/ehealth/api/prescriptions"), status=401, payload={})
            client = FarmadClient(session, access_token=ACCESS, refresh_token=REFRESH)
            with pytest.raises(FarmadEhealthAuthorizationRequiredError):
                await client.async_get_prescriptions()
    assert client.refresh_token == REFRESH


async def test_get_prescription_not_found_is_none() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(ehealth_url("/ehealth/api/prescriptions/BEP10S18PLM4"), status=404, payload={})
            client = FarmadClient(session, access_token=ACCESS, refresh_token=REFRESH)
            prescription = await client.async_get_prescription("BEP10S18PLM4")
    assert prescription is None


@pytest.mark.parametrize("body", ["", "[]", '"text"'], ids=["empty", "list", "string"])
@pytest.mark.parametrize(
    ("url", "call"),
    [
        (
            alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}"),
            lambda client: client.async_get_account(),
        ),
        (
            alb_url(f"/usermanagement/api/organization/{APB}"),
            lambda client: client.async_get_organization(APB),
        ),
        (
            alb_url(f"/patientmanagement/api/patients/{PATIENT_ID}"),
            lambda client: client.async_get_patient(),
        ),
        (
            alb_url(f"/customerbasket/api/{APB}/pharmacypreferences/for-customer"),
            lambda client: client.async_get_pharmacy_preferences(APB),
        ),
        (
            catalog_url("/api/catalog/products/kava/3093242"),
            lambda client: client.async_get_kava_product("3093242"),
        ),
    ],
    ids=["account", "organization", "patient", "pharmacy_preferences", "kava_product"],
)
async def test_single_object_endpoint_rejects_a_non_object_answer(
    url: Any, call: Callable[[FarmadClient], Any], body: str
) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(url, body=body)
            with pytest.raises(FarmadInvalidResponseError, match="not a JSON object"):
                await call(make_client(session))


@pytest.mark.parametrize("body", ["", "[]"], ids=["empty", "list"])
async def test_get_baskets_with_a_non_object_answer_is_empty(body: str) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(alb_url(f"/customerbasket/api/{APB}/customerbaskets"), body=body)
            baskets = await make_client(session).async_get_baskets(APB)
    assert baskets == ()


async def test_not_found_after_a_refresh_is_none() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(catalog_url(f"/api/catalog/products/0000000/{APB}"), status=401, payload={})
            m.get(catalog_url(f"/api/catalog/products/0000000/{APB}"), status=404, payload={})
            m.post(
                "https://signin.procura.farmad.be/oauth/token",
                payload={"access_token": "fresh-access", "refresh_token": "fresh-refresh"},
            )
            product = await make_client(session).async_get_product_in_apb(APB, "0000000")
    assert product is None


async def test_link_pharmacy_pending_acceptance_is_false() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}/self-onboarding"),
                status=202,
                body="",
            )
            linked = await make_client(session).async_link_pharmacy("344107")
    assert linked is False


async def test_link_pharmacy_with_explicit_account_id() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(alb_url("/usermanagement/api/account/other-account/self-onboarding"), body="")
            linked = await make_client(session).async_link_pharmacy(
                "344107", account_id="other-account"
            )
    assert linked is True
