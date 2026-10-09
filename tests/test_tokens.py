"""Token lifecycle tests: expiry, rotation, delivery ordering."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import aiohttp
import pytest
from aioresponses import CallbackResult, aioresponses

from aiofarmad._tokens import TokenLifecycle, _jwt_claim, _jwt_expiry, _jwt_payload
from aiofarmad.exceptions import FarmadAuthenticationError

from .conftest import TOKEN_URL, make_jwt
from .conftest import b64 as _b64


@pytest.fixture
async def session_provider() -> AsyncIterator[Callable[[], aiohttp.ClientSession]]:
    async with aiohttp.ClientSession() as session:
        yield lambda: session


async def test_claims_from_access_token(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(
        session_provider=session_provider, timeout=5.0, access_token=make_jwt()
    )
    assert lifecycle.account_id is not None
    assert lifecycle.patient_id is not None
    assert lifecycle.expiry is not None
    assert lifecycle.expiry > datetime.now(UTC)


async def test_expiry_is_none_without_token(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(session_provider=session_provider, timeout=5.0)
    assert lifecycle.access_token is None
    assert lifecycle.refresh_token is None
    assert lifecycle.expiry is None
    assert lifecycle.account_id is None
    assert lifecycle.patient_id is None
    assert not lifecycle.is_expired(datetime.now(UTC))


async def test_is_expired_requires_aware_datetime(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(
        session_provider=session_provider, timeout=5.0, access_token=make_jwt()
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        lifecycle.is_expired(datetime.now())  # noqa: DTZ005


async def test_bearer_without_token_raises(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(session_provider=session_provider, timeout=5.0)
    with pytest.raises(FarmadAuthenticationError, match="Not authenticated"):
        lifecycle.bearer()


async def test_ensure_fresh_refreshes_expired_token(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(
        session_provider=session_provider,
        timeout=5.0,
        access_token=make_jwt(exp_offset=-100.0),
        refresh_token="rotating-refresh",
    )
    with aioresponses() as m:
        m.post(
            TOKEN_URL,
            payload={"access_token": "fresh-access", "refresh_token": "next-refresh"},
        )
        await lifecycle.ensure_fresh()
    assert lifecycle.access_token == "fresh-access"
    assert lifecycle.refresh_token == "next-refresh"


async def test_ensure_fresh_keeps_live_token(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(
        session_provider=session_provider,
        timeout=5.0,
        access_token=make_jwt(),
        refresh_token="rotating-refresh",
    )
    await lifecycle.ensure_fresh()
    assert lifecycle.access_token is not None
    assert lifecycle.refresh_token == "rotating-refresh"


async def test_ensure_fresh_without_refresh_token_is_noop(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(session_provider=session_provider, timeout=5.0, access_token=None)
    await lifecycle.ensure_fresh()
    assert lifecycle.access_token is None


async def test_refresh_without_token_raises(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(session_provider=session_provider, timeout=5.0)
    with pytest.raises(FarmadAuthenticationError, match="No refresh token"):
        await lifecycle.refresh()


async def test_refresh_returns_the_rotated_pair(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(
        session_provider=session_provider,
        timeout=5.0,
        access_token=make_jwt(),
        refresh_token="rotating-refresh",
    )
    with aioresponses() as m:
        m.post(
            TOKEN_URL,
            payload={"access_token": "fresh-access", "refresh_token": "next-refresh"},
        )
        access, refresh = await lifecycle.refresh()
    assert access == "fresh-access"
    assert refresh == "next-refresh"


async def test_concurrent_refresh_rotates_once(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(
        session_provider=session_provider,
        timeout=5.0,
        access_token=make_jwt(),
        refresh_token="rotating-refresh",
    )
    gate = asyncio.Event()

    async def gated_token(_url: object, **_kwargs: object) -> object:
        await gate.wait()
        return CallbackResult(
            status=200,
            payload={"access_token": "once-access", "refresh_token": "once-refresh"},
        )

    with aioresponses() as m:
        m.post(TOKEN_URL, callback=gated_token)
        first = asyncio.create_task(lifecycle.refresh())
        await asyncio.sleep(0)
        second = asyncio.create_task(lifecycle.refresh())
        await asyncio.sleep(0)
        gate.set()
        results = await asyncio.gather(first, second)
        token_posts = next(entries for key, entries in m.requests.items() if key[0] == "POST")
    assert {access for access, _refresh in results} == {"once-access"}
    assert lifecycle.refresh_token == "once-refresh"
    assert len(token_posts) == 1


async def test_rotation_delivery_order_and_superseded_drops(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    delivered: list[str] = []

    async def on_rotation(access_token: str, _refresh_token: str | None) -> None:
        delivered.append(access_token)

    lifecycle = TokenLifecycle(
        session_provider=session_provider,
        timeout=5.0,
        refresh_token="rotating-refresh",
        on_rotation=on_rotation,
    )
    with aioresponses() as m:
        m.post(
            TOKEN_URL, payload={"access_token": "first-access", "refresh_token": "first-refresh"}
        )
        await lifecycle.refresh()
        m.post(
            TOKEN_URL, payload={"access_token": "second-access", "refresh_token": "second-refresh"}
        )
        await lifecycle.refresh()
    assert delivered == ["first-access", "second-access"]


async def test_failing_callback_does_not_break_rotation(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    calls: list[str] = []

    async def failing_on_rotation(access_token: str, _refresh_token: str | None) -> None:
        calls.append(access_token)
        msg = "consumer storage broke"
        raise RuntimeError(msg)

    lifecycle = TokenLifecycle(
        session_provider=session_provider,
        timeout=5.0,
        refresh_token="rotating-refresh",
        on_rotation=failing_on_rotation,
    )
    with aioresponses() as m:
        m.post(TOKEN_URL, payload={"access_token": "a1", "refresh_token": "r1"})
        await lifecycle.refresh()
        m.post(TOKEN_URL, payload={"access_token": "a2", "refresh_token": "r2"})
        await lifecycle.refresh()
    assert calls == ["a1", "a2"]
    assert lifecycle.access_token == "a2"


def test_jwt_expiry_ignores_malformed_tokens() -> None:
    assert _jwt_expiry("not-a-jwt") is None
    assert _jwt_expiry("a.bm90LWpzb24.c") is None
    assert _jwt_expiry("a.eyJzdWIiOiJ4In0.c") is None


async def test_ensure_fresh_refreshes_missing_token(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(
        session_provider=session_provider, timeout=5.0, refresh_token="rotating-refresh"
    )
    with aioresponses() as m:
        m.post(
            TOKEN_URL, payload={"access_token": "fresh-access", "refresh_token": "fresh-refresh"}
        )
        await lifecycle.ensure_fresh()
    assert lifecycle.access_token == "fresh-access"


async def test_sequential_refresh_rotates_again(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    lifecycle = TokenLifecycle(
        session_provider=session_provider,
        timeout=5.0,
        access_token=make_jwt(),
        refresh_token="rotating-refresh",
    )
    with aioresponses() as m:
        m.post(TOKEN_URL, payload={"access_token": "a1", "refresh_token": "r1"})
        m.post(TOKEN_URL, payload={"access_token": "a2", "refresh_token": "r2"})
        first = await lifecycle.refresh()
        second = await lifecycle.refresh()
    assert first == ("a1", "r1")
    assert second == ("a2", "r2")
    assert lifecycle.access_token == "a2"


async def test_superseded_rotations_are_dropped_from_delivery(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    delivered: list[str] = []
    gate = asyncio.Event()

    async def on_rotation(access_token: str, _refresh_token: str | None) -> None:
        delivered.append(access_token)
        if len(delivered) == 1:
            await gate.wait()

    lifecycle = TokenLifecycle(
        session_provider=session_provider,
        timeout=5.0,
        on_rotation=on_rotation,
    )
    delivery = asyncio.create_task(lifecycle.adopt("a1", "r1"))
    await asyncio.sleep(0)
    await lifecycle.adopt("a2", "r2")
    await lifecycle.adopt("a3", "r3")
    gate.set()
    await delivery
    assert delivered == ["a1", "a3"]


async def test_claim_helpers_reject_hostile_payloads(
    session_provider: Callable[[], aiohttp.ClientSession],
) -> None:
    assert _jwt_payload("one-two") is None
    assert _jwt_payload("a.W10.c") is None
    assert _jwt_claim("one-two", "claim") is None

    huge = make_jwt(exp_offset=1e30)
    assert _jwt_expiry(huge) is None

    header = "e30"
    payload = _b64(
        json.dumps(
            {
                "exp": "not-a-number",
                "http://schemas.microsoft.com/ws/2008/06/identity/claims/accountId": 5,
            }
        ).encode()
    )
    token = f"{header}.{payload}.sig"
    assert _jwt_expiry(token) is None
    lifecycle = TokenLifecycle(session_provider=session_provider, timeout=5.0, access_token=token)
    assert lifecycle.expiry is None
    assert lifecycle.account_id is None
