"""Dump every live payload the account can reach into captures/."""

import asyncio
import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import aiohttp

from aiofarmad import FarmadClient

APB = "343602"
ALB = "https://alb-prod.procura.farmad.be"
CAPTURES = Path("captures")


def load_env() -> dict[str, str]:
    """Read every key from the local .env file."""
    raw = Path(".env").read_text()
    return dict(re.findall(r"^([A-Z_]+)=(.*)$", raw, re.MULTILINE))


def week_window() -> tuple[str, str]:
    """The window from last Monday to next Sunday."""
    today = datetime.now(UTC).date()
    monday = today - timedelta(days=today.weekday())
    start = datetime(monday.year, monday.month, monday.day, tzinfo=UTC)
    end = start + timedelta(days=7) - timedelta(milliseconds=1)
    from_z = start.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    until_z = end.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return from_z, until_z


def save(name: str, payload: Any, status: int) -> None:
    """Write one raw payload under captures/."""
    CAPTURES.mkdir(exist_ok=True)
    target = CAPTURES / f"{name}_raw.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print("captured", name, status, "->", target.name)


async def raw_get(session: aiohttp.ClientSession, access_token: str, path: str) -> tuple[int, Any]:
    """Fetch one path with the bearer token and return status with payload."""
    async with session.get(
        f"{ALB}{path}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    ) as response:
        text = await response.text()
        if not text.strip():
            return response.status, None
        return response.status, json.loads(text)


async def main() -> None:
    env = load_env()
    start, end = week_window()
    async with (
        aiohttp.ClientSession() as session,
        FarmadClient(
            session,
            email=env["EMAIL"],
            password=env["PASSWORD"],
        ) as client,
    ):
        await client.async_login()
        access = client.access_token or ""
        account_id = client.account_id or ""
        patient_id = client.patient_id or ""

        calls: list[tuple[str, str]] = [
            ("account", f"/usermanagement/api/account/{account_id}?api-version=8.12"),
            ("organization", f"/usermanagement/api/organization/{APB}?api-version=8.12"),
            ("patient", f"/patientmanagement/api/patients/{patient_id}?api-version=2.0"),
            (
                "patientcontents",
                f"/patientmanagement/api/patientcontents/{APB}/{patient_id}?api-version=2.0",
            ),
            (
                "pharmacy_preferences",
                f"/customerbasket/api/{APB}/pharmacypreferences/for-customer?api-version=1.0",
            ),
            (
                "scheme_day",
                (
                    f"/medicationscheme/api/medicationscheme/{patient_id}/scheme/{APB}/day"
                    f"?from={start}&until={end}&language=nl&api-version=2.5"
                ),
            ),
            (
                "scheme_nondaily",
                (
                    f"/medicationscheme/api/medicationscheme/{patient_id}/scheme/{APB}/nondaily"
                    f"?day={date.today().isoformat()}"  # noqa: DTZ011
                    f"T00:00:00.000Z&language=nl&api-version=2.5"
                ),
            ),
            (
                "baskets",
                (
                    f"/customerbasket/api/{APB}/customerbaskets"
                    f"?PatientId={patient_id}&Skip=0&Take=50&api-version=1.0"
                ),
            ),
            (
                "conversations",
                f"/messaging/api/message/{APB}?Limit=25&Page=0&api-version=4.0",
            ),
        ]
        for name, path in calls:
            status, payload = await raw_get(session, access, path)
            save(name, payload, status)
            if name == "conversations" and isinstance(payload, list):
                for conversation in payload:
                    customer_account_id = conversation.get("customerId")
                    if not isinstance(customer_account_id, str):
                        continue
                    status, messages = await raw_get(
                        session,
                        access,
                        f"/messaging/api/message/{APB}/{customer_account_id}"
                        f"?Limit=25&Page=0&api-version=4.0",
                    )
                    save(f"conversation_messages_{customer_account_id}", messages, status)


asyncio.run(main())
