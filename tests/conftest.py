"""Shared fixtures, JWT helpers, and login-flow mocks for aiofarmad tests."""

import base64
import inspect
import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import aiohttp
import pytest
from aiohttp import ClientResponse
from aioresponses import aioresponses
from aioresponses import core as _aioresponses_core

from aiofarmad.const import AUTH0_DOMAIN, AUTH_REDIRECT_URI

FIXTURES_DIR = Path(__file__).parent / "fixtures"

AUTHORIZE_URL = f"https://{AUTH0_DOMAIN}/authorize"
LOGIN_URL = f"https://{AUTH0_DOMAIN}/login"
PASSWORD_POST_URL = f"https://{AUTH0_DOMAIN}/usernamepassword/login"
WS_FED_CALLBACK_URL = f"https://{AUTH0_DOMAIN}/login/callback"
RESUME_URL = f"https://{AUTH0_DOMAIN}/authorize/resume"
TOKEN_URL = f"https://{AUTH0_DOMAIN}/oauth/token"

LOGIN_STATE = "login-state-token"
CSRF = "csrf-token-value"
AUTH_CODE = "test-authorization-code"
WS_FED_ACTION = f"https://{AUTH0_DOMAIN}/login/callback"

USERNAME = "user@example.com"
PASSWORD = "hunter2"

ACCOUNT_ID = "0b6f1b28-0000-4000-8000-000000000001"
PATIENT_ID = "1c7a2c39-0000-4000-8000-000000000002"
APB = "343602"

TOKEN_RESPONSE = {
    "access_token": "new-access-token",
    "refresh_token": "new-refresh-token",
    "expires_in": "36000",
    "scope": "openid profile email offline_access",
    "token_type": "Bearer",
}


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def make_jwt(
    *,
    account_id: str = ACCOUNT_ID,
    patient_id: str | None = PATIENT_ID,
    exp_offset: float = 36000.0,
) -> str:
    """Build an unsigned JWT carrying the Farmad claims."""
    header = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = {
        "sub": "auth0|test",
        "exp": int(time.time() + exp_offset),
        "http://schemas.microsoft.com/ws/2008/06/identity/claims/accountId": account_id,
    }
    if patient_id is not None:
        payload["http://schemas.microsoft.com/ws/2008/06/identity/claims/patient"] = patient_id
    encoded = b64(json.dumps(payload).encode())
    return f"{header}.{encoded}.signature"


def expired_jwt() -> str:
    return make_jwt(exp_offset=-3600.0)


def _q(url: str) -> re.Pattern[str]:
    """Match ``url`` regardless of its query string."""
    return re.compile(rf"^{re.escape(url)}(\?.*)?$")


def _lock_page(*, state: str = LOGIN_STATE, csrf: str = CSRF) -> str:
    config = {
        "auth0Domain": AUTH0_DOMAIN,
        "clientID": "5xlNthD37j7PK1vItdDKFC9H3cV0s8FN",
        "extraParams": {
            "state": state,
            "_csrf": csrf,
            "code_challenge": "challenge-placeholder",
            "response_type": "code",
            "scope": "openid profile email offline_access",
            "audience": "api://procura.farmad.be",
        },
    }
    blob = base64.b64encode(json.dumps(config).encode()).decode()
    return (
        f"<html><script>var config = JSON.parse("
        f"decodeURIComponent(escape(window.atob('{blob}'))));</script></html>"
    )


def _ws_fed_page() -> str:
    return (
        '<form method="post" name="hiddenform" '
        f'action="{WS_FED_ACTION}">'
        '<input type="hidden" name="wa" value="wsignin1.0">'
        '<input type="hidden" name="wresult" value="token-payload"/>'
        '<input type="hidden" name="wctx" value="context-payload"/>'
        "</form>"
    )


def callback_url(code: str = AUTH_CODE) -> str:
    return f"{AUTH_REDIRECT_URI}?code={code}&state={LOGIN_STATE}"


def register_login_flow(m: aioresponses, *, token_response: dict[str, str] | None = None) -> None:
    """Mock every hop of the scripted Lock login."""
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
    m.get(
        _q(RESUME_URL),
        status=302,
        headers={"Location": callback_url()},
        body="",
    )
    m.post(_q(TOKEN_URL), payload=token_response or TOKEN_RESPONSE)


@pytest.fixture
def load_fixture() -> Callable[[str], Any]:
    """Return a helper that loads a JSON fixture by name."""

    def _load(name: str) -> Any:
        return json.loads((FIXTURES_DIR / name).read_text())

    return _load


@pytest.fixture
def created_sessions(monkeypatch: pytest.MonkeyPatch) -> list[aiohttp.ClientSession]:
    """Track every aiohttp session the library creates."""
    created: list[aiohttp.ClientSession] = []
    real_session_cls = aiohttp.ClientSession

    def _tracking_factory(*args: Any, **kwargs: Any) -> aiohttp.ClientSession:
        session = real_session_cls(*args, **kwargs)
        created.append(session)
        return session

    monkeypatch.setattr(aiohttp, "ClientSession", _tracking_factory)
    return created


_original_build_response = _aioresponses_core.RequestMatch._build_response


def _build_response_with_stream_writer(self: Any, *args: Any, **kwargs: Any) -> Any:
    response_class = kwargs.get("response_class") or ClientResponse
    if "stream_writer" in inspect.signature(response_class).parameters:

        class _StreamWriterCompatResponse(response_class):  # type: ignore[misc, valid-type]
            def __init__(self, *a: Any, **kw: Any) -> None:
                kw.setdefault("stream_writer", Mock(output_size=0))
                super().__init__(*a, **kw)

        kwargs["response_class"] = _StreamWriterCompatResponse
    return _original_build_response(self, *args, **kwargs)


_aioresponses_core.RequestMatch._build_response = _build_response_with_stream_writer  # type: ignore[method-assign]


def fixture_path(name: str) -> Path:
    """Return the path of one fixture file."""
    return FIXTURES_DIR / name


def alb_url(path: str) -> re.Pattern[str]:
    """Match one ALB path regardless of its query string."""
    return re.compile(rf"^https://alb-prod\.procura\.farmad\.be{re.escape(path)}(\?.*)?$")


def ehealth_url(path: str) -> re.Pattern[str]:
    """Match one eHealth path regardless of its query string."""
    return re.compile(rf"^https://procura\.farmad\.be{re.escape(path)}(\?.*)?$")


def cast_response(payload: Any) -> dict[str, Any]:
    """Narrow a loaded fixture to a JSON object."""
    return cast("dict[str, Any]", payload)
