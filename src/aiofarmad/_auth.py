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

_OTP_CHALLENGE_PATH = "/u/mfa-otp-challenge"
_MAX_REDIRECT_HOPS = 5

_WS_FED_INPUT = re.compile(r"<input[^>]*name=\"([^\"]+)\"[^>]*value=\"([^\"]*)\"")
_LOCK_CONFIG = re.compile(r"window\.atob\('([^']+)'\)")


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
    decoded = base64.b64decode(match.group(1))
    config = json.loads(decoded)
    if not isinstance(config, dict):
        msg = "The hosted login page carried an unusable configuration"
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

    try:
        async with asyncio.timeout(timeout):
            location = await _first_location(session, url)
            outcome: str | _OtpChallenge
            if location.startswith(AUTH_REDIRECT_URI):
                outcome = _code_from_callback(location)
            else:
                location = await _post_credentials(session, location, email, password)
                outcome = await _resolve_login_outcome(session, location)
        if isinstance(outcome, _OtpChallenge):
            if otp_provider is None:
                msg = "The account requires a one-time code, so pass otp_provider"
                raise FarmadMfaRequiredError(msg)
            otp = await otp_provider()
            async with asyncio.timeout(timeout):
                outcome = await _complete_challenge(session, outcome, otp)
    except TimeoutError as err:
        msg = "Login timed out"
        raise FarmadTimeoutError(msg) from err
    except aiohttp.ClientError as err:
        msg = f"Login failed: {err}"
        raise FarmadCommunicationError(msg) from err

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
    session: aiohttp.ClientSession,
    login_location: str,
    email: str,
    password: str,
) -> str:
    """Submit the credentials to the hosted login form and return where the login continues."""
    login_url = _absolute(login_location)
    async with session.get(
        login_url,
        headers={"User-Agent": USER_AGENT},
        allow_redirects=True,
    ) as response:
        login_page = await response.text()

    config = _lock_config(login_page)
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

    async with session.post(
        f"https://{AUTH0_DOMAIN}/usernamepassword/login",
        data=form,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": f"https://{AUTH0_DOMAIN}",
            "Referer": login_url,
            "User-Agent": USER_AGENT,
        },
        allow_redirects=False,
    ) as response:
        status = response.status
        body = await response.text()

    if status == HTTPStatus.UNAUTHORIZED:
        msg = "Wrong email or password"
        raise FarmadAuthenticationError(msg)
    if status != HTTPStatus.OK:
        msg = f"The hosted login form rejected the request with {status}"
        raise FarmadAuthenticationError(msg)

    action_match = re.search(r"action=\"([^\"]+)\"", body)
    fields = _hidden_fields(body)
    if action_match is None or "wresult" not in fields:
        msg = "The hosted login form answered with an unexpected page"
        raise FarmadAuthenticationError(msg)

    async with session.post(
        action_match.group(1),
        data=fields,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": f"https://{AUTH0_DOMAIN}",
            "Referer": f"https://{AUTH0_DOMAIN}/login",
            "User-Agent": USER_AGENT,
        },
        allow_redirects=False,
    ) as response:
        await response.read()
        return response.headers.get("Location", "")


async def _resolve_login_outcome(
    session: aiohttp.ClientSession,
    location: str,
) -> str | _OtpChallenge:
    """Follow the login redirects until the callback or the one-time-code page."""
    for _ in range(_MAX_REDIRECT_HOPS):
        if not location:
            msg = "The login stopped before reaching the callback"
            raise FarmadAuthenticationError(msg)
        if location.startswith(AUTH_REDIRECT_URI):
            return _code_from_callback(location)
        if _OTP_CHALLENGE_PATH in location:
            return await _read_challenge(session, location)
        location = await _hop(session, location, f"https://{AUTH0_DOMAIN}/login")
    msg = "The login followed too many redirects before reaching the callback"
    raise FarmadAuthenticationError(msg)


async def _read_challenge(session: aiohttp.ClientSession, location: str) -> _OtpChallenge:
    """Read the one-time-code page and return the challenge it carries."""
    challenge_url = _absolute(location)
    async with session.get(
        challenge_url,
        headers={"Referer": f"https://{AUTH0_DOMAIN}/login", "User-Agent": USER_AGENT},
        allow_redirects=False,
    ) as response:
        body = await response.text()
    state = _hidden_fields(body).get("state")
    if not state:
        msg = "The one-time-code page did not carry its state"
        raise FarmadAuthenticationError(msg)
    return _OtpChallenge(url=challenge_url, state=state)


async def _complete_challenge(
    session: aiohttp.ClientSession,
    challenge: _OtpChallenge,
    otp: str,
) -> str:
    """Submit the one-time code and return the authorization code."""
    async with session.post(
        challenge.url,
        data={"state": challenge.state, "code": otp},
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": f"https://{AUTH0_DOMAIN}",
            "Referer": challenge.url,
            "User-Agent": USER_AGENT,
        },
        allow_redirects=False,
    ) as response:
        status = response.status
        location = response.headers.get("Location", "")
    if status != HTTPStatus.FOUND:
        msg = "Wrong one-time code"
        raise FarmadAuthenticationError(msg)
    outcome = await _resolve_login_outcome(session, location)
    if isinstance(outcome, _OtpChallenge):
        msg = "Wrong one-time code"
        raise FarmadAuthenticationError(msg)
    return outcome


async def _hop(session: aiohttp.ClientSession, location: str, referer: str) -> str:
    """Request one redirect hop and return the next location."""
    async with session.get(
        _absolute(location),
        headers={"Referer": referer, "User-Agent": USER_AGENT},
        allow_redirects=False,
    ) as response:
        await response.read()
        return response.headers.get("Location", "")


async def _first_location(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(
        url,
        headers={"User-Agent": USER_AGENT},
        allow_redirects=False,
    ) as response:
        await response.read()
        location = response.headers.get("Location", "")
    if not location:
        msg = "The authorize endpoint did not redirect to a login page"
        raise FarmadAuthenticationError(msg)
    return location


def _absolute(location: str) -> str:
    if location.startswith("/"):
        return f"https://{AUTH0_DOMAIN}{location}"
    return location


def _code_from_callback(location: str) -> str:
    code = parse_qs(urlparse(location).query).get("code", [""])[0]
    if not code:
        msg = "The callback did not carry an authorization code"
        raise FarmadAuthenticationError(msg)
    return code
