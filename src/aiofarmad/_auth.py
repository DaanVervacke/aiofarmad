"""The scripted Auth0 Lock login: PKCE, the hosted form, the code step, and the token exchange."""

import asyncio
import base64
import hashlib
import html
import json
import re
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp

from ._oauth import async_request_tokens
from ._transport import request
from .const import (
    AUTH0_AUDIENCE,
    AUTH0_CLIENT_ID,
    AUTH0_CONNECTION,
    AUTH0_DOMAIN,
    AUTH0_SCOPE,
    AUTH0_TENANT,
    AUTH_REDIRECT_URI,
    AUTH_UI_LOCALES,
    USER_AGENT,
)
from .exceptions import (
    FarmadAuthenticationError,
    FarmadCommunicationError,
    FarmadMfaRequiredError,
    FarmadTimeoutError,
)

OtpProvider = Callable[[], Awaitable[str]]

_AUTHORIZE_PARAMS = {
    "response_type": "code",
    "client_id": AUTH0_CLIENT_ID,
    "redirect_uri": AUTH_REDIRECT_URI,
    "scope": AUTH0_SCOPE,
    "audience": AUTH0_AUDIENCE,
    "response_mode": "query",
    "ui_locales": AUTH_UI_LOCALES,
}

_ORIGIN = f"https://{AUTH0_DOMAIN}"
_LOGIN_PAGE_URL = f"{_ORIGIN}/login"
_OTP_CHALLENGE_PATH = "/u/mfa-otp-challenge"
_MAX_REDIRECT_HOPS = 5

_WS_FED_INPUT = re.compile(r"<input[^>]*name=\"([^\"]+)\"[^>]*value=\"([^\"]*)\"")
_LOCK_CONFIG = re.compile(r"window\.atob\('([^']+)'\)")


@dataclass(frozen=True, slots=True)
class _Reply:
    """The parts of one hosted login answer the flow reads."""

    status: int
    location: str
    body: str


@dataclass(frozen=True, slots=True)
class _Browser:
    """Send hosted login requests with the headers the app's browser sends."""

    session: aiohttp.ClientSession
    timeout: float

    async def get(self, url: str, *, referer: str | None = None, follow: bool = False) -> _Reply:
        """Request one login page."""
        headers = {"User-Agent": USER_AGENT}
        if referer is not None:
            headers["Referer"] = referer
        return await self._send("GET", url, headers, form=None, follow=follow)

    async def post(self, url: str, form: dict[str, str], *, referer: str) -> _Reply:
        """Submit one login form."""
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": _ORIGIN,
            "Referer": referer,
        }
        return await self._send("POST", url, headers, form=form, follow=False)

    async def _send(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        *,
        form: dict[str, str] | None,
        follow: bool,
    ) -> _Reply:
        async with request(
            self.session,
            method=method,
            url=url,
            headers=headers,
            form_body=form,
            allow_redirects=follow,
            raise_on_error=False,
            timeout=self.timeout,
        ) as response:
            return _Reply(
                status=response.status,
                location=response.headers.get("Location", ""),
                body=await response.text(errors="replace"),
            )


@dataclass(frozen=True, slots=True)
class _OtpChallenge:
    """The pending one-time-code page the hosted login issued."""

    url: str
    state: str


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _hidden_fields(body: str) -> dict[str, str]:
    return {name: html.unescape(value) for name, value in _WS_FED_INPUT.findall(body)}


def _lock_config(body: str) -> dict[str, Any]:
    match = _LOCK_CONFIG.search(body)
    if match is None:
        msg = "The hosted login page did not carry its configuration"
        raise FarmadAuthenticationError(msg)
    msg = "The hosted login page carried an unusable configuration"
    try:
        config = json.loads(base64.b64decode(match.group(1)))
    except ValueError as err:
        raise FarmadAuthenticationError(msg) from err
    if not isinstance(config, dict):
        raise FarmadAuthenticationError(msg)
    return config


async def async_login(
    session: aiohttp.ClientSession,
    email: str,
    password: str,
    timeout: float,  # noqa: ASYNC109
    otp_provider: OtpProvider | None = None,
) -> dict[str, str]:
    """Log in with the hosted login form and return the issued token fields.

    The otp provider is awaited only when the account requires a
    one-time code, and its wait does not count against the timeout.
    """
    verifier = secrets.token_urlsafe(64)[:86]
    params = dict(_AUTHORIZE_PARAMS)
    params["code_challenge"] = _code_challenge(verifier)
    params["code_challenge_method"] = "S256"
    url = f"https://{AUTH0_DOMAIN}/authorize?{urlencode(params)}"
    browser = _Browser(session, timeout)

    try:
        async with asyncio.timeout(timeout):
            location = await _first_location(browser, url)
            outcome: str | _OtpChallenge
            if location.startswith(AUTH_REDIRECT_URI):
                outcome = _code_from_callback(location)
            else:
                location = await _post_credentials(browser, location, email, password)
                outcome = await _resolve_login_outcome(browser, location)
        if isinstance(outcome, _OtpChallenge):
            if otp_provider is None:
                msg = "The account requires a one-time code, so pass otp_provider"
                raise FarmadMfaRequiredError(msg)
            otp = await otp_provider()
            async with asyncio.timeout(timeout):
                outcome = await _complete_challenge(browser, outcome, otp)
    except (TimeoutError, FarmadTimeoutError) as err:
        msg = "Login timed out"
        raise FarmadTimeoutError(msg) from err

    return await async_request_tokens(
        session,
        {
            "grant_type": "authorization_code",
            "client_id": AUTH0_CLIENT_ID,
            "code_verifier": verifier,
            "code": outcome,
            "redirect_uri": AUTH_REDIRECT_URI,
        },
        timeout=timeout,
    )


async def _post_credentials(
    browser: _Browser,
    login_location: str,
    email: str,
    password: str,
) -> str:
    """Submit the credentials to the hosted login form and return where the login continues."""
    login_url = _absolute(login_location)
    page = await browser.get(login_url, follow=True)
    if page.status != HTTPStatus.OK:
        msg = f"The hosted login page answered {page.status}"
        raise FarmadCommunicationError(msg, status=page.status)

    config = _lock_config(page.body)
    extra_params = config.get("extraParams", {})
    if not isinstance(extra_params, dict):
        msg = "The hosted login page carried unusable login parameters"
        raise FarmadAuthenticationError(msg)
    csrf = extra_params.get("_csrf")
    state = extra_params.get("state")
    challenge = extra_params.get("code_challenge")
    if not isinstance(csrf, str) or not isinstance(state, str) or not isinstance(challenge, str):
        msg = "The hosted login page did not carry its login state"
        raise FarmadAuthenticationError(msg)

    form = {
        "username": email,
        "password": password,
        "client_id": AUTH0_CLIENT_ID,
        "tenant": AUTH0_TENANT,
        "connection": AUTH0_CONNECTION,
        "redirect_uri": AUTH_REDIRECT_URI,
        "protocol": "oauth2",
        "response_type": "code",
        "scope": AUTH0_SCOPE,
        "audience": AUTH0_AUDIENCE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "response_mode": "query",
        "ui_locales": AUTH_UI_LOCALES,
        "_csrf": csrf,
        "state": state,
    }
    answer = await browser.post(f"{_ORIGIN}/usernamepassword/login", form, referer=login_url)
    if answer.status == HTTPStatus.UNAUTHORIZED:
        msg = "Wrong email or password"
        raise FarmadAuthenticationError(msg)
    if answer.status != HTTPStatus.OK:
        msg = f"The hosted login form rejected the request with {answer.status}"
        raise FarmadAuthenticationError(msg)

    action_match = re.search(r"action=\"([^\"]+)\"", answer.body)
    fields = _hidden_fields(answer.body)
    if action_match is None or "wresult" not in fields:
        msg = "The hosted login form answered with an unexpected page"
        raise FarmadAuthenticationError(msg)

    callback = await browser.post(action_match.group(1), fields, referer=_LOGIN_PAGE_URL)
    return callback.location


async def _resolve_login_outcome(browser: _Browser, location: str) -> str | _OtpChallenge:
    """Follow the login redirects until the callback or the one-time-code page."""
    for _ in range(_MAX_REDIRECT_HOPS):
        if not location:
            msg = "The login stopped before reaching the callback"
            raise FarmadAuthenticationError(msg)
        if location.startswith(AUTH_REDIRECT_URI):
            return _code_from_callback(location)
        if _OTP_CHALLENGE_PATH in location:
            return await _read_challenge(browser, location)
        hop = await browser.get(_absolute(location), referer=_LOGIN_PAGE_URL)
        location = hop.location
    msg = "The login followed too many redirects before reaching the callback"
    raise FarmadAuthenticationError(msg)


async def _read_challenge(browser: _Browser, location: str) -> _OtpChallenge:
    """Read the one-time-code page and return the challenge it carries."""
    challenge_url = _absolute(location)
    page = await browser.get(challenge_url, referer=_LOGIN_PAGE_URL)
    state = _hidden_fields(page.body).get("state")
    if not state:
        msg = "The one-time-code page did not carry its state"
        raise FarmadAuthenticationError(msg)
    return _OtpChallenge(url=challenge_url, state=state)


async def _complete_challenge(browser: _Browser, challenge: _OtpChallenge, otp: str) -> str:
    """Submit the one-time code and return the authorization code."""
    answer = await browser.post(
        challenge.url, {"state": challenge.state, "code": otp}, referer=challenge.url
    )
    if answer.status != HTTPStatus.FOUND:
        msg = "Wrong one-time code"
        raise FarmadAuthenticationError(msg)
    outcome = await _resolve_login_outcome(browser, answer.location)
    if isinstance(outcome, _OtpChallenge):
        msg = "Wrong one-time code"
        raise FarmadAuthenticationError(msg)
    return outcome


async def _first_location(browser: _Browser, url: str) -> str:
    first = await browser.get(url)
    if not first.location:
        msg = "The authorize endpoint did not redirect to a login page"
        raise FarmadAuthenticationError(msg)
    return first.location


def _absolute(location: str) -> str:
    if location.startswith("/"):
        return f"{_ORIGIN}{location}"
    return location


def _code_from_callback(location: str) -> str:
    code = parse_qs(urlparse(location).query).get("code", [""])[0]
    if not code:
        msg = "The callback did not carry an authorization code"
        raise FarmadAuthenticationError(msg)
    return code
