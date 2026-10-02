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
CATALOG = "https://api.catalog.procura.farmad.be"
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


async def raw_get(session: aiohttp.ClientSession, access_token: str, url: str) -> tuple[int, Any]:
    """Fetch one URL with the bearer token and return status with payload."""
    async with session.get(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    ) as response:
        text = await response.text()
        if not text.strip():
            return response.status, None
        return response.status, json.loads(text)


def first_ordered_cnk(payload: Any) -> str | None:
    """Return the CNK of the first line in the first submitted order."""
    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        return None
    lines = results[0].get("customerBasketLines")
    if not isinstance(lines, list) or not lines or not isinstance(lines[0], dict):
        return None
    product = lines[0].get("product")
    if not isinstance(product, dict):
        return None
    cnk = product.get("cnk")
    return cnk if isinstance(cnk, str) and cnk else None


def first_gtin(payload: Any) -> str | None:
    """Return the first GTIN code of one product payload."""
    if not isinstance(payload, dict):
        return None
    codes = payload.get("productCodes")
    if not isinstance(codes, list):
        return None
    for code in codes:
        if not isinstance(code, dict) or code.get("codeType") != "Gtin":
            continue
        value = code.get("codeValue")
        if isinstance(value, str) and value:
            return value
    return None


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
            ("account", f"{ALB}/usermanagement/api/account/{account_id}?api-version=8.12"),
            (
                "organization",
                f"{ALB}/usermanagement/api/organization/{APB}?api-version=8.12",
            ),
            (
                "patient",
                f"{ALB}/patientmanagement/api/patients/{patient_id}?api-version=2.0",
            ),
            (
                "patientcontents",
                f"{ALB}/patientmanagement/api/patientcontents/{APB}/{patient_id}?api-version=2.0",
            ),
            (
                "pharmacy_preferences",
                f"{ALB}/customerbasket/api/{APB}/pharmacypreferences/for-customer?api-version=1.0",
            ),
            (
                "scheme_day",
                (
                    f"{ALB}/medicationscheme/api/medicationscheme/{patient_id}/scheme/{APB}/day"
                    f"?from={start}&until={end}&language=nl&api-version=2.5"
                ),
            ),
            (
                "scheme_nondaily",
                (
                    f"{ALB}/medicationscheme/api/medicationscheme/{patient_id}"
                    f"/scheme/{APB}/nondaily?day={date.today().isoformat()}"  # noqa: DTZ011
                    "T00:00:00.000Z&language=nl&api-version=2.5"
                ),
            ),
            (
                "scheme_product",
                (
                    f"{ALB}/medicationscheme/api/medicationscheme/{patient_id}"
                    f"/scheme/{APB}/product/2810901?language=nl&api-version=2.5"
                ),
            ),
            (
                "baskets",
                (
                    f"{ALB}/customerbasket/api/{APB}/customerbaskets"
                    f"?PatientId={patient_id}&Skip=0&Take=50&api-version=1.0"
                ),
            ),
            (
                "conversations",
                f"{ALB}/messaging/api/message/{APB}?Limit=25&Page=0&api-version=4.0",
            ),
            (
                "message_draft",
                f"{ALB}/messaging/api/draft/{APB}/{account_id}?api-version=4.0",
            ),
            (
                "service_messages",
                f"{ALB}/notifications/api/servicemessages?api-version=2.1",
            ),
            (
                "technical_interruptions",
                f"{ALB}/notifications/api/technicalinterruptions?api-version=2.1",
            ),
            (
                "products_search",
                (
                    f"{CATALOG}/api/catalog/products?SearchTerm=paracetamol&Apb={APB}"
                    "&Page=1&Limit=3&Language=nl&api-version=5.3"
                ),
            ),
            (
                "kava_product",
                f"{CATALOG}/api/catalog/products/kava/2810901?api-version=5.3",
            ),
        ]
        baskets_payload: Any = None
        for name, url in calls:
            status, payload = await raw_get(session, access, url)
            save(name, payload, status)
            if name == "baskets":
                baskets_payload = payload
            if name == "conversations" and isinstance(payload, list):
                for conversation in payload:
                    customer_account_id = conversation.get("customerId")
                    if not isinstance(customer_account_id, str):
                        continue
                    status, messages = await raw_get(
                        session,
                        access,
                        f"{ALB}/messaging/api/message/{APB}/{customer_account_id}"
                        f"?Limit=25&Page=0&api-version=4.0",
                    )
                    save(f"conversation_messages_{customer_account_id}", messages, status)

        cnk = first_ordered_cnk(baskets_payload)
        if cnk:
            status, product = await raw_get(
                session,
                access,
                f"{CATALOG}/api/catalog/products/{cnk}/{APB}?api-version=5.3",
            )
            save("product_in_apb", product, status)
            gtin = first_gtin(product)
            if gtin:
                status, by_gtin = await raw_get(
                    session,
                    access,
                    f"{CATALOG}/api/catalog/products/gtin/{gtin}/{APB}?api-version=5.3",
                )
                save("product_in_apb_by_gtin", by_gtin, status)


asyncio.run(main())
