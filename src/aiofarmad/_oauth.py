"""The OAuth token endpoint primitive shared by login and refresh."""

import asyncio
from typing import Any

import aiohttp

from .const import AUTH0_DOMAIN, USER_AGENT
from .exceptions import (
    FarmadAuthenticationError,
    FarmadCommunicationError,
    FarmadInvalidResponseError,
    FarmadTimeoutError,
)

TOKEN_URL = f"https://{AUTH0_DOMAIN}/oauth/token"


async def async_request_tokens(
    session: aiohttp.ClientSession,
    body: dict[str, Any],
    timeout: float,  # noqa: ASYNC109
) -> dict[str, str]:
    """Post a token request and return the token fields as strings."""
    try:
        async with (
            asyncio.timeout(timeout),
            session.post(
                TOKEN_URL,
                json=body,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            ) as response,
        ):
            payload = await response.json(content_type=None)
    except TimeoutError as err:
        msg = "Token request timed out"
        raise FarmadTimeoutError(msg) from err
    except aiohttp.ClientError as err:
        msg = f"Token request failed: {err}"
        raise FarmadCommunicationError(msg) from err
    except ValueError as err:
        msg = "Token endpoint answered with a body that is not JSON"
        raise FarmadInvalidResponseError(msg) from err
    if not isinstance(payload, dict):
        msg = "Token endpoint answered with JSON that is not an object"
        raise FarmadInvalidResponseError(msg)
    if "access_token" not in payload:
        raise FarmadAuthenticationError(_auth_error_message(payload))
    return {
        key: str(value)
        for key, value in payload.items()
        if isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool))
    }


def _auth_error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    description = payload.get("error_description")
    if isinstance(error, str) and isinstance(description, str):
        return f"Token request rejected: {description} ({error})"
    if isinstance(error, str):
        return f"Token request rejected: {error}"
    return "Token request answered without an access token"
