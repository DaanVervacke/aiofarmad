"""Attempt to capture eHealth prescription payloads with a consent session.

The platform currently rejects every non-browser client for eHealth, so this
script ends in FarmadEhealthAuthorizationRequiredError. It exists to retest
that gate after Farmad changes: put a live consent cookie in .env as
EHEALTH_COOKIE and run it.
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import aiohttp

from aiofarmad import FarmadClient


def load_env() -> dict[str, str]:
    """Read every key from the local .env file."""
    raw = Path(".env").read_text()
    return dict(re.findall(r"^([A-Z_]+)=(.*)$", raw, re.MULTILINE))


async def fetch() -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None, Any]:
    """Run the library reads and return the raw payloads."""
    env = load_env()
    async with (
        aiohttp.ClientSession() as session,
        FarmadClient(
            session,
            email=env["EMAIL"],
            password=env["PASSWORD"],
            ehealth_cookie=env["EHEALTH_COOKIE"],
        ) as client,
    ):
        await client.async_login()
        prescriptions = await client.async_get_prescriptions()
        items = [prescription.raw for prescription in prescriptions if prescription.raw]
        single = await client.async_get_prescription("BEP10S18PLM4")
        return items, single.raw if single is not None else None, items


def main() -> None:
    """Write the captured payloads under captures/."""
    items, single, _items = asyncio.run(fetch())
    if items is None or single is None:
        msg = "the eHealth session did not return any payload"
        raise SystemExit(msg)
    Path("captures/prescriptions_raw.json").write_text(json.dumps(items, indent=2) + "\n")
    Path("captures/prescription_raw.json").write_text(json.dumps(single, indent=2) + "\n")
    print("captured", len(items), "prescriptions")
    print("single keys:", sorted(single.keys()))


if __name__ == "__main__":
    main()
