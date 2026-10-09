"""HTTP plumbing: session ownership and the request and JSON helpers."""

import asyncio
import json
import logging
import socket
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any
from urllib.parse import urlsplit

import aiohttp

from .exceptions import (
    FarmadAuthenticationError,
    FarmadAuthorizationError,
    FarmadCommunicationError,
    FarmadError,
    FarmadInvalidResponseError,
    FarmadNotFoundError,
    FarmadTimeoutError,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class OwnedSession:
    """A ClientSession plus whether this library created and must close it."""

    session: aiohttp.ClientSession
    owned: bool

    async def close_if_owned(self) -> None:
        """Close the session when this library created it."""
        if self.owned:
            await self.session.close()


@asynccontextmanager
async def request(
    session: aiohttp.ClientSession,
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    form_body: aiohttp.FormData | dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    allow_redirects: bool = False,
    raise_on_error: bool = True,
    timeout: float = 30.0,  # noqa: ASYNC109
) -> AsyncIterator[aiohttp.ClientResponse]:
    """Perform one HTTP request and map failures to library exceptions."""
    try:
        started = time.monotonic()
        async with asyncio.timeout(timeout):
            async with session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_body,
                data=form_body,
                params=params,
                allow_redirects=allow_redirects,
            ) as response:
                split = urlsplit(url)
                _LOGGER.debug(
                    "%s %s%s -> %s in %.3fs",
                    method,
                    split.netloc,
                    split.path,
                    response.status,
                    time.monotonic() - started,
                )
                if raise_on_error:
                    await _raise_for_status(response)
                yield response
    except FarmadError:
        raise
    except TimeoutError as exc:
        msg = f"Timeout communicating with the Farmad API ({exc.__class__.__name__})"
        raise FarmadTimeoutError(msg) from exc
    except (aiohttp.ClientError, socket.gaierror) as exc:
        msg = f"Error communicating with the Farmad API ({exc.__class__.__name__})"
        raise FarmadCommunicationError(msg) from exc


async def _raise_for_status(response: aiohttp.ClientResponse) -> None:
    if response.status == HTTPStatus.UNAUTHORIZED:
        msg = "The Farmad API rejected the token (401)"
        raise FarmadAuthenticationError(msg, status=401)
    if response.status == HTTPStatus.FORBIDDEN:
        msg = "The account is not allowed to use this pharmacy feature (403)"
        raise FarmadAuthorizationError(msg, status=403)
    if response.status == HTTPStatus.NOT_FOUND:
        msg = "The Farmad API has no such object (404)"
        raise FarmadNotFoundError(msg, status=404)
    if response.status >= HTTPStatus.BAD_REQUEST:
        detail = await _error_detail(response)
        msg = f"Farmad API error {response.status}"
        if detail:
            msg = f"{msg}: {detail}"
        raise FarmadCommunicationError(msg, status=response.status)


_ERROR_DETAIL_LIMIT = 200


async def _error_detail(response: aiohttp.ClientResponse) -> str:
    try:
        text = await response.text()
    except aiohttp.ClientError, UnicodeDecodeError:
        return ""
    if len(text) > _ERROR_DETAIL_LIMIT:
        return text[:_ERROR_DETAIL_LIMIT]
    return text.strip()


async def request_json(
    session: aiohttp.ClientSession,
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    form_body: aiohttp.FormData | None = None,
    params: dict[str, str] | None = None,
    timeout: float = 30.0,  # noqa: ASYNC109
) -> Any:
    """Make a request and return the parsed JSON body."""
    _status, payload = await request_json_with_status(
        session,
        method=method,
        url=url,
        headers=headers,
        json_body=json_body,
        form_body=form_body,
        params=params,
        timeout=timeout,
    )
    return payload


async def request_json_with_status(
    session: aiohttp.ClientSession,
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    form_body: aiohttp.FormData | None = None,
    params: dict[str, str] | None = None,
    timeout: float = 30.0,  # noqa: ASYNC109
) -> tuple[int, Any]:
    """Make a request and return the HTTP status with the parsed JSON body."""
    async with request(
        session,
        method=method,
        url=url,
        headers=headers,
        json_body=json_body,
        form_body=form_body,
        params=params,
        timeout=timeout,
    ) as response:
        return response.status, await json_payload(response)


async def json_payload(response: aiohttp.ClientResponse) -> Any:
    """Parse the response body as JSON of any shape, returning None for an empty body."""
    try:
        text = await response.text()
    except aiohttp.ClientError as exc:
        msg = "Response body could not be read"
        raise FarmadInvalidResponseError(msg) from exc
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except ValueError as exc:
        msg = "Response body is not valid JSON"
        raise FarmadInvalidResponseError(msg) from exc
