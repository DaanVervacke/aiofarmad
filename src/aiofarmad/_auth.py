"""The scripted Auth0 Lock login: PKCE, the hosted login form, and the code exchange."""

import asyncio
import base64
import hashlib
import html
import json
import logging
import re
import secrets
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

_LOGGER = logging.getLogger(__name__)

_AUTHORIZE_PARAMS = {
    "response_type": "code",
    "client_id": AUTH0_CLIENT_ID,
    "redirect_uri": AUTH_REDIRECT_URI,
    "scope": AUTH0_SCOPE,
    "audience": AUTH0_AUDIENCE,
    "response_mode": "query",
    "ui_locales": AUTH_UI_LOCALES,
}

_WS_FED_INPUT = re.compile(r"<input[^>]*name=\"([^\"]+)\"[^>]*value=\"([^\"]*)\"")
_LOCK_CONFIG = re.compile(r"window\.atob\('([^']+)'\)")


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
) -> dict[str, str]:
    """Log in with the hosted login form and return the issued token fields."""
    verifier = secrets.token_urlsafe(64)[:86]
    params = dict(_AUTHORIZE_PARAMS)
    params["code_challenge"] = _code_challenge(verifier)
    params["code_challenge_method"] = "S256"
    url = f"https://{AUTH0_DOMAIN}/authorize?{urlencode(params)}"

    async with asyncio.timeout(timeout):
        try:
            code = await _resolve_authorization_code(session, url, email, password)
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
            "code": code,
            "redirect_uri": AUTH_REDIRECT_URI,
        },
        timeout=timeout,
    )


async def _resolve_authorization_code(
    session: aiohttp.ClientSession,
    authorize_url: str,
    email: str,
    password: str,
) -> str:
    location = await _first_location(session, authorize_url)
    if location.startswith(AUTH_REDIRECT_URI):
        return _code_from_callback(location)

    login_url = f"https://{AUTH0_DOMAIN}{location}"
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
        msg = (
            "The login answered with an unexpected page, which means multi-factor "
            "authentication or another interactive step is required"
        )
        raise FarmadMfaRequiredError(msg)

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
        location = response.headers.get("Location", "")

    for _ in range(5):
        if not location:
            msg = "The login stopped before reaching the callback"
            raise FarmadAuthenticationError(msg)
        if location.startswith(AUTH_REDIRECT_URI):
            return _code_from_callback(location)
        async with session.get(
            _absolute(location),
            headers={"Referer": f"https://{AUTH0_DOMAIN}/login", "User-Agent": USER_AGENT},
            allow_redirects=False,
        ) as response:
            await response.read()
            location = response.headers.get("Location", "")

    msg = "The login followed too many redirects before reaching the callback"
    raise FarmadAuthenticationError(msg)


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
