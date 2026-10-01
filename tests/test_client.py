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
    FarmadNotFoundError,
)

from .conftest import (
    ACCOUNT_ID,
    APB,
    PASSWORD,
    PATIENT_ID,
    USERNAME,
    alb_url,
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


async def test_link_pharmacy_posts_apb() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(alb_url(f"/usermanagement/api/account/{ACCOUNT_ID}/self-onboarding"), payload={})
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
