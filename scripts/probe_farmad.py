"""Live probe: run every read endpoint against the real Farmad API."""

import asyncio
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import aiohttp

from aiofarmad import (
    FarmadAuthorizationError,
    FarmadClient,
    FarmadError,
)

APB = "343602"


def load_credentials() -> dict[str, str]:
    """Read EMAIL and PASSWORD from the local .env file."""
    raw = Path(".env").read_text()
    return dict(re.findall(r"^([A-Z]+)=(.*)$", raw, re.MULTILINE))


def week_window() -> tuple[datetime, datetime]:
    """The window from last Monday to next Sunday."""
    today = datetime.now(UTC).date()
    monday = today - timedelta(days=today.weekday())
    start = datetime(monday.year, monday.month, monday.day, tzinfo=UTC)
    end = start + timedelta(days=7) - timedelta(milliseconds=1)
    return start, end


async def main() -> None:
    credentials = load_credentials()
    async with (
        aiohttp.ClientSession() as session,
        FarmadClient(
            session,
            email=credentials["EMAIL"],
            password=credentials["PASSWORD"],
        ) as client,
    ):
        await client.async_login()
        print("login ok, account:", client.account_id, "patient:", client.patient_id)

        account = await client.async_get_account()
        print("account:", account.full_name, "pharmacies:", account.entitled_pharmacies)

        patient = await client.async_get_patient()
        print("patient:", patient.patient_id, "records:", len(patient.pharmacies))

        organization = await client.async_get_organization(APB)
        print("pharmacy:", organization.name, organization.city)

        preferences = await client.async_get_pharmacy_preferences(APB)
        print("preferences:", preferences)

        from_, until = week_window()
        scheme = await client.async_get_medication_day_scheme(APB, from_=from_, until=until)
        total = sum(day.medication_count for day in scheme)
        print("day schemes:", len(scheme), "intakes:", total)
        for day in scheme:
            moments = ", ".join(m.title for m in day.intake_moments) or "none"
            print(f"  {day.date}: {moments}")

        nondaily = await client.async_get_medication_nondaily_products(
            APB,
            day=date.today(),  # noqa: DTZ011
        )
        print("nondaily products:", len(nondaily))

        baskets = await client.async_get_baskets(APB)
        print("baskets:", len(baskets))

        draft = await client.async_get_draft_basket(APB)
        print("draft:", "none" if draft is None else draft.id)

        try:
            conversations = await client.async_get_conversations(APB)
            print("conversations:", len(conversations))
        except FarmadAuthorizationError:
            print("conversations: not allowed (messaging needs a patient file at the pharmacy)")

        print("refresh token present:", client.refresh_token is not None)


try:
    asyncio.run(main())
except FarmadError as err:
    print("probe failed:", err)
    raise
