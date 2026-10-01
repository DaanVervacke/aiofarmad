"""Transport tests: error mapping, ownership, and payload handling."""

import aiohttp
import pytest
from aioresponses import aioresponses

from aiofarmad._transport import (
    OwnedSession,
    json_payload,
    request,
    request_json,
)
from aiofarmad.exceptions import (
    FarmadAuthenticationError,
    FarmadAuthorizationError,
    FarmadCommunicationError,
    FarmadInvalidResponseError,
    FarmadNotFoundError,
    FarmadTimeoutError,
)

BASE = "https://alb-prod.procura.farmad.be"


async def test_owned_session_closes_only_what_it_created() -> None:
    async with aiohttp.ClientSession() as outer:
        owned = OwnedSession(session=outer, owned=False)
        await owned.close_if_owned()
        assert not outer.closed
    created = aiohttp.ClientSession()
    owned = OwnedSession(session=created, owned=True)
    await owned.close_if_owned()
    assert created.closed


async def test_request_maps_status_errors() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(f"{BASE}/a", status=401)
            m.get(f"{BASE}/b", status=403)
            m.get(f"{BASE}/c", status=404)
            m.get(f"{BASE}/d", status=500)
            with pytest.raises(FarmadAuthenticationError):
                async with request(session, method="GET", url=f"{BASE}/a"):
                    pass
            with pytest.raises(FarmadAuthorizationError):
                async with request(session, method="GET", url=f"{BASE}/b"):
                    pass
            with pytest.raises(FarmadNotFoundError):
                async with request(session, method="GET", url=f"{BASE}/c"):
                    pass
            with pytest.raises(FarmadCommunicationError):
                async with request(session, method="GET", url=f"{BASE}/d"):
                    pass


async def test_request_error_statuses_do_not_raise_when_disabled() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(f"{BASE}/e", status=500, body="broken")
            async with request(
                session,
                method="GET",
                url=f"{BASE}/e",
                raise_on_error=False,
            ) as response:
                assert response.status == 500


async def test_request_maps_timeout() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(f"{BASE}/f", exception=TimeoutError())
            with pytest.raises(FarmadTimeoutError):
                async with request(session, method="GET", url=f"{BASE}/f", timeout=0.01):
                    pass


async def test_request_maps_client_errors() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(f"{BASE}/g", exception=aiohttp.ClientError("boom"))
            with pytest.raises(FarmadCommunicationError):
                async with request(session, method="GET", url=f"{BASE}/g"):
                    pass


async def test_json_payload_returns_none_for_empty_body() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.delete(f"{BASE}/k", status=200, body="")
            m.get(f"{BASE}/l", payload={"x": 1})
            assert await request_json(session, method="DELETE", url=f"{BASE}/k") is None
            assert await request_json(session, method="GET", url=f"{BASE}/l") == {"x": 1}


async def test_request_json_sends_params_and_body() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.post(f"{BASE}/m?api-version=1.0", payload={"id": "new"})
            result = await request_json(
                session,
                method="POST",
                url=f"{BASE}/m",
                params={"api-version": "1.0"},
                json_body={"patientId": "p"},
            )
            assert result == {"id": "new"}
            request_log = m.requests
            key = next(
                k for k in request_log if k[0] == "POST" and str(k[1]).startswith(f"{BASE}/m")
            )
            assert request_log[key][0].kwargs["json"] == {"patientId": "p"}


async def test_request_json_timeout_raises_farmad_timeout() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(f"{BASE}/slow", exception=TimeoutError())
            with pytest.raises(FarmadTimeoutError):
                await request_json(session, method="GET", url=f"{BASE}/slow")


async def test_json_payload_maps_read_failures() -> None:
    class _FailingResponse:
        async def text(self) -> str:
            msg = "boom"
            raise aiohttp.ClientPayloadError(msg)

    with pytest.raises(FarmadInvalidResponseError, match="could not be read"):
        await json_payload(_FailingResponse())  # type: ignore[arg-type]


async def test_request_json_rejects_invalid_json() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(f"{BASE}/broken", body="not-json-at-all")
            with pytest.raises(FarmadInvalidResponseError, match="not valid JSON"):
                await request_json(session, method="GET", url=f"{BASE}/broken")


async def test_error_message_carries_body_detail() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(
                f"{BASE}/rejected",
                status=400,
                body='{"title":"Bad Request","detail":"online payments are off"}',
            )
            with pytest.raises(FarmadCommunicationError, match="online payments are off"):
                await request_json(session, method="GET", url=f"{BASE}/rejected")


async def test_error_message_survives_binary_body() -> None:
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(f"{BASE}/binary", status=500, body=b"\xff\xfe\x00garbage")
            with pytest.raises(FarmadCommunicationError, match="Farmad API error 500"):
                await request_json(session, method="GET", url=f"{BASE}/binary")


async def test_error_detail_is_truncated() -> None:
    long_body = "x" * 500
    async with aiohttp.ClientSession() as session:
        with aioresponses() as m:
            m.get(f"{BASE}/long", status=500, body=long_body)
            with pytest.raises(FarmadCommunicationError) as excinfo:
                await request_json(session, method="GET", url=f"{BASE}/long")
    message = str(excinfo.value)
    assert "x" * 200 in message
    assert "x" * 201 not in message
