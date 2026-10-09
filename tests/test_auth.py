"""Login flow tests: every hop, plus every failure mode."""

import asyncio
import base64
import json
import re

import aiohttp
import pytest
from aioresponses import aioresponses
from yarl import URL

from aiofarmad._auth import async_login
from aiofarmad.exceptions import (
    FarmadAuthenticationError,
    FarmadCommunicationError,
    FarmadMfaRequiredError,
    FarmadTimeoutError,
)

from .conftest import (
    AUTHORIZE_URL,
    CSRF,
    LOGIN_STATE,
    LOGIN_URL,
    OTP,
    OTP_CHALLENGE_LOCATION,
    OTP_CHALLENGE_URL,
    OTP_STATE,
    PASSWORD,
    PASSWORD_POST_URL,
    RESUME_URL,
    TOKEN_RESPONSE,
    TOKEN_URL,
    USERNAME,
    WS_FED_ACTION,
    WS_FED_CALLBACK_URL,
    callback_url,
    otp_challenge_page,
    register_login_flow,
)


def _q(url: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(url)}(\?.*)?$")


async def test_login_walks_every_hop() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            register_login_flow(m)
            tokens = await async_login(session, USERNAME, PASSWORD, timeout=5.0)
    assert tokens["access_token"] == "new-access-token"
    assert tokens["refresh_token"] == "new-refresh-token"
    assert tokens["scope"] == "openid profile email offline_access"


async def test_login_posts_lock_form_fields() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            register_login_flow(m)
            await async_login(session, USERNAME, PASSWORD, timeout=5.0)
            requests = m.requests
            password_posts = requests.get(("POST", URL(PASSWORD_POST_URL)))
    assert password_posts is not None
    form = dict(password_posts[0].kwargs["data"])
    assert form["username"] == USERNAME
    assert form["password"] == PASSWORD
    assert form["connection"] == "Username-Password-Authentication"
    assert form["tenant"] == "production-farmad"
    assert form["_csrf"] == CSRF
    assert form["state"] == LOGIN_STATE


async def test_login_with_wrong_password_raises() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body=_lock_page())
            m.post(_q(PASSWORD_POST_URL), status=401, payload={"error": "invalid_user_password"})
            with pytest.raises(FarmadAuthenticationError, match="Wrong email or password"):
                await async_login(session, USERNAME, "bad", timeout=5.0)


async def test_login_with_unexpected_password_answer_raises() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body=_lock_page())
            m.post(_q(PASSWORD_POST_URL), body="<html>an unexpected page</html>")
            with pytest.raises(FarmadAuthenticationError, match="unexpected page"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_mfa_login_walks_every_hop() -> None:
    calls: list[str] = []

    async def provider() -> str:
        calls.append("called")
        return OTP

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            register_login_flow(m, mfa=True)
            tokens = await async_login(
                session, USERNAME, PASSWORD, timeout=5.0, otp_provider=provider
            )
            requests = m.requests
            otp_posts = requests.get(("POST", URL(OTP_CHALLENGE_URL)))
    assert tokens["access_token"] == "new-access-token"
    assert tokens["refresh_token"] == "new-refresh-token"
    assert calls == ["called"]
    assert otp_posts is not None
    form = dict(otp_posts[0].kwargs["data"])
    assert form["code"] == OTP
    assert form["state"] == OTP_STATE


async def test_mfa_login_without_provider_raises() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            register_login_flow(m, mfa=True)
            with pytest.raises(FarmadMfaRequiredError, match="one-time code"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_mfa_login_with_rejected_code_raises() -> None:
    async def provider() -> str:
        return OTP

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            register_login_flow(m, mfa=True, otp_rejected=True)
            with pytest.raises(FarmadAuthenticationError, match="Wrong one-time code"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0, otp_provider=provider)


async def test_mfa_login_with_repeated_challenge_raises() -> None:
    async def provider() -> str:
        return OTP

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body=_lock_page())
            m.post(_q(PASSWORD_POST_URL), body=_ws_fed_page())
            m.post(
                _q(WS_FED_CALLBACK_URL),
                status=302,
                headers={"Location": "/authorize/resume?state=resume-state"},
                body="",
            )
            m.get(_q(RESUME_URL), status=302, headers={"Location": OTP_CHALLENGE_LOCATION}, body="")
            m.get(_q(OTP_CHALLENGE_URL), body=otp_challenge_page())
            m.post(
                _q(OTP_CHALLENGE_URL),
                status=302,
                headers={"Location": "/authorize/resume?state=resume-after-otp"},
                body="",
            )
            m.get(_q(RESUME_URL), status=302, headers={"Location": OTP_CHALLENGE_LOCATION}, body="")
            m.get(_q(OTP_CHALLENGE_URL), body=otp_challenge_page())
            with pytest.raises(FarmadAuthenticationError, match="Wrong one-time code"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0, otp_provider=provider)


async def test_mfa_challenge_without_state_raises() -> None:
    async def provider() -> str:
        return OTP

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body=_lock_page())
            m.post(_q(PASSWORD_POST_URL), body=_ws_fed_page())
            m.post(
                _q(WS_FED_CALLBACK_URL),
                status=302,
                headers={"Location": "/authorize/resume?state=resume-state"},
                body="",
            )
            m.get(_q(RESUME_URL), status=302, headers={"Location": OTP_CHALLENGE_LOCATION}, body="")
            m.get(
                _q(OTP_CHALLENGE_URL), body='<html><form><input name="code" value=""></form></html>'
            )
            with pytest.raises(FarmadAuthenticationError, match="did not carry its state"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0, otp_provider=provider)


async def test_mfa_provider_wait_is_not_limited_by_the_timeout() -> None:
    async def slow_provider() -> str:
        await asyncio.sleep(0.2)
        return OTP

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            register_login_flow(m, mfa=True)
            tokens = await async_login(
                session, USERNAME, PASSWORD, timeout=0.05, otp_provider=slow_provider
            )
    assert tokens["access_token"] == "new-access-token"


async def test_login_without_mfa_never_awaits_the_otp_provider() -> None:
    calls: list[str] = []

    async def provider() -> str:
        calls.append("called")
        return OTP

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            register_login_flow(m)
            tokens = await async_login(
                session, USERNAME, PASSWORD, timeout=5.0, otp_provider=provider
            )
    assert tokens["access_token"] == "new-access-token"
    assert calls == []


async def test_login_without_lock_config_raises() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body="<html>no config here</html>")
            with pytest.raises(FarmadAuthenticationError, match="did not carry"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_without_authorize_redirect_raises() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(_q(AUTHORIZE_URL), status=200, body="<html>hello</html>")
            with pytest.raises(FarmadAuthenticationError, match="did not redirect"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_with_active_session_skips_the_form() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": callback_url()},
                body="",
            )
            m.post(_q(TOKEN_URL), payload=TOKEN_RESPONSE)
            tokens = await async_login(session, USERNAME, PASSWORD, timeout=5.0)
    assert tokens["access_token"] == "new-access-token"


async def test_login_without_callback_code_raises() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"{callback_url().rsplit('?', 1)[0]}?state=x"},
                body="",
            )
            with pytest.raises(FarmadAuthenticationError, match="authorization code"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_stops_when_a_hop_has_no_location() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body=_lock_page(), repeat=True)
            m.post(_q(PASSWORD_POST_URL), body=_ws_fed_page())
            m.post(
                _q(WS_FED_CALLBACK_URL),
                status=302,
                headers={"Location": "/authorize/resume?state=resume-state"},
                body="",
            )
            m.get(_q(RESUME_URL), status=302, headers={"Location": ""}, body="", repeat=True)
            with pytest.raises(
                FarmadAuthenticationError, match="stopped before reaching the callback"
            ):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_gives_up_on_redirect_loops() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body=_lock_page(), repeat=True)
            m.post(_q(PASSWORD_POST_URL), body=_ws_fed_page())
            m.post(
                _q(WS_FED_CALLBACK_URL),
                status=302,
                headers={"Location": "/authorize/resume?state=resume-state"},
                body="",
            )
            m.get(
                _q(RESUME_URL),
                status=302,
                headers={"Location": "/authorize/resume"},
                body="",
                repeat=True,
            )
            with pytest.raises(FarmadAuthenticationError, match="too many redirects"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_maps_transport_errors() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(_q(AUTHORIZE_URL), exception=aiohttp.ClientError("boom"))
            with pytest.raises(FarmadCommunicationError):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_rejects_non_object_lock_config() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body=_config_page(["not", "a", "dict"]))
            with pytest.raises(FarmadAuthenticationError, match="unusable configuration"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_rejects_non_object_extra_params() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body=_config_page({"extraParams": ["nope"]}))
            with pytest.raises(FarmadAuthenticationError, match="unusable login parameters"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_rejects_missing_login_state() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(
                _q(LOGIN_URL),
                body=_config_page({"extraParams": {"_csrf": "c", "code_challenge": "x"}}),
            )
            with pytest.raises(FarmadAuthenticationError, match="did not carry its login state"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_maps_timeout() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(_q(AUTHORIZE_URL), exception=TimeoutError())
            with pytest.raises(FarmadTimeoutError, match="Login timed out"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_rejects_unexpected_form_status() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body=_lock_page(), repeat=True)
            m.post(_q(PASSWORD_POST_URL), status=503, body="")
            with pytest.raises(FarmadAuthenticationError, match="rejected the request with 503"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_follows_absolute_hop_locations() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body=_lock_page(), repeat=True)
            m.post(_q(PASSWORD_POST_URL), body=_ws_fed_page())
            m.post(
                _q(WS_FED_CALLBACK_URL),
                status=302,
                headers={"Location": "https://signin.procura.farmad.be/authorize/resume?state=x"},
                body="",
            )
            m.get(_q(RESUME_URL), status=302, headers={"Location": callback_url()}, body="")
            m.post(_q(TOKEN_URL), payload=TOKEN_RESPONSE)
            tokens = await async_login(session, USERNAME, PASSWORD, timeout=5.0)
    assert tokens["access_token"] == "new-access-token"


def _lock_page() -> str:
    config = {
        "extraParams": {
            "state": LOGIN_STATE,
            "_csrf": CSRF,
            "code_challenge": "challenge-placeholder",
        }
    }
    blob = base64.b64encode(json.dumps(config).encode()).decode()
    return f"<html><script>window.atob('{blob}');</script></html>"


def _ws_fed_page() -> str:
    return (
        f'<form method="post" action="{WS_FED_ACTION}">'
        '<input type="hidden" name="wa" value="wsignin1.0">'
        '<input type="hidden" name="wresult" value="t"/>'
        '<input type="hidden" name="wctx" value="c"/>'
        "</form>"
    )


def _config_page(config: object) -> str:
    blob = base64.b64encode(json.dumps(config).encode()).decode()
    return f"<html><script>window.atob('{blob}');</script></html>"


@pytest.mark.parametrize(
    "page",
    [
        "<html><script>window.atob('not base64!');</script></html>",
        f"<html><script>window.atob('{base64.b64encode(b'{not json').decode()}');</script></html>",
        f"<html><script>window.atob('{base64.b64encode(b'\xff\xfe').decode()}');</script></html>",
    ],
    ids=["not_base64", "not_json", "not_utf8"],
)
async def test_login_rejects_an_undecodable_lock_config(page: str) -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), body=page)
            with pytest.raises(FarmadAuthenticationError, match="unusable configuration"):
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)


async def test_login_rejects_a_failing_login_page() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                _q(AUTHORIZE_URL),
                status=302,
                headers={"Location": f"/login?state={LOGIN_STATE}"},
                body="",
            )
            m.get(_q(LOGIN_URL), status=503, body="")
            with pytest.raises(FarmadCommunicationError, match="login page answered 503") as err:
                await async_login(session, USERNAME, PASSWORD, timeout=5.0)
    assert err.value.status == 503
