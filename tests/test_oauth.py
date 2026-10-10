"""Token endpoint tests."""

import asyncio

import aiohttp
import pytest
from aioresponses import aioresponses

from aiofarmad._oauth import async_request_tokens
from aiofarmad.const import USER_AGENT
from aiofarmad.exceptions import (
    FarmadAuthenticationError,
    FarmadCommunicationError,
    FarmadInvalidResponseError,
    FarmadTimeoutError,
)

from .conftest import TOKEN_URL

BODY = {
    "grant_type": "authorization_code",
    "client_id": "5xlNthD37j7PK1vItdDKFC9H3cV0s8FN",
    "code": "code",
    "code_verifier": "verifier",
    "redirect_uri": "https://procura.farmad.be/auth-callback.html",
}


async def test_request_tokens_happy_path() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                TOKEN_URL,
                payload={"access_token": "a", "refresh_token": "r", "expires_in": "36000"},
            )
            tokens = await async_request_tokens(session, BODY, timeout=5.0)
    assert tokens == {"access_token": "a", "refresh_token": "r", "expires_in": "36000"}


async def test_request_tokens_keeps_an_integer_expiry_and_drops_other_types() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                TOKEN_URL,
                payload={
                    "access_token": "a",
                    "expires_in": 36000,
                    "flag": True,
                    "nested": {"x": 1},
                },
            )
            tokens = await async_request_tokens(session, BODY, timeout=5.0)
    assert tokens == {"access_token": "a", "expires_in": "36000"}


async def test_request_tokens_deadline_raises_the_library_timeout() -> None:
    async def slow(_url: object, **_kwargs: object) -> None:
        await asyncio.sleep(1)

    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(TOKEN_URL, callback=slow, payload={"access_token": "a"})
            with pytest.raises(FarmadTimeoutError):
                await async_request_tokens(session, BODY, timeout=0.01)


async def test_request_tokens_error_payload() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(
                TOKEN_URL,
                payload={
                    "error": "unauthorized_client",
                    "error_description": "Grant type not allowed",
                },
            )
            with pytest.raises(FarmadAuthenticationError, match="Grant type not allowed"):
                await async_request_tokens(session, BODY, timeout=5.0)


async def test_request_tokens_error_without_description() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(TOKEN_URL, payload={"error": "access_denied"})
            with pytest.raises(FarmadAuthenticationError, match="access_denied"):
                await async_request_tokens(session, BODY, timeout=5.0)


async def test_request_tokens_without_access_token() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(TOKEN_URL, payload={"foo": "bar"})
            with pytest.raises(FarmadAuthenticationError, match="without an access token"):
                await async_request_tokens(session, BODY, timeout=5.0)


async def test_request_tokens_non_object_payload() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(TOKEN_URL, body='["a"]')
            with pytest.raises(FarmadInvalidResponseError):
                await async_request_tokens(session, BODY, timeout=5.0)


async def test_request_tokens_non_json_body() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(TOKEN_URL, body="<html>server error</html>")
            with pytest.raises(FarmadInvalidResponseError, match="not JSON"):
                await async_request_tokens(session, BODY, timeout=5.0)


async def test_request_tokens_timeout() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(TOKEN_URL, exception=TimeoutError())
            with pytest.raises(FarmadTimeoutError):
                await async_request_tokens(session, BODY, timeout=5.0)


async def test_request_tokens_transport_error() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(TOKEN_URL, exception=aiohttp.ClientError("boom"))
            with pytest.raises(FarmadCommunicationError):
                await async_request_tokens(session, BODY, timeout=5.0)


async def test_request_tokens_sends_the_app_user_agent() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(TOKEN_URL, payload={"access_token": "a", "refresh_token": "r"})
            await async_request_tokens(session, BODY, timeout=5.0)
            calls = next(iter(m.requests.values()))
    assert calls[0].kwargs["headers"]["User-Agent"] == USER_AGENT
