"""Place one real order through the library, then cancel it."""

import asyncio
import re
from pathlib import Path

import aiohttp

from aiofarmad import DraftProduct, FarmadClient, FarmadError

APB = "343602"
PRODUCT_CNK = "3093242"
PRODUCT_PRICE = 3.10
PRODUCT_DESCRIPTION = "Febelcare sterile gauze compresses"


def load_credentials() -> dict[str, str]:
    """Read EMAIL and PASSWORD from the local .env file."""
    raw = Path(".env").read_text()
    return dict(re.findall(r"^([A-Z]+)=(.*)$", raw, re.MULTILINE))


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
        print("login ok for account", client.account_id)

        draft = await client.async_get_draft_basket(APB)
        if draft is not None:
            print("existing draft found, clearing it first")
            await client.async_clear_draft_basket(APB)

        products = (DraftProduct(product_cnk=PRODUCT_CNK, quantity=1),)
        draft_id = await client.async_save_draft_basket(APB, products=products)
        print("draft created:", draft_id)
        if draft_id is None:
            msg = "the draft was created but no id came back"
            raise RuntimeError(msg)

        basket_id = await client.async_submit_basket(
            APB,
            draft_id,
            products=products,
            unit_prices=((PRODUCT_CNK, PRODUCT_PRICE),),
        )
        print("order submitted, basket id:", basket_id)

        baskets = await client.async_get_baskets(APB)
        for basket in baskets:
            print(
                "basket:",
                basket.id,
                basket.state,
                basket.customer_patient_name,
                "items:",
                basket.item_count,
            )

        target = basket_id or (baskets[0].id if baskets else None)
        if target is None:
            print("no basket to cancel")
            return
        await client.async_cancel_basket(APB, target)
        print("order cancelled:", target)

        baskets = await client.async_get_baskets(APB)
        for basket in baskets:
            print("after cancel:", basket.id, basket.state)


try:
    asyncio.run(main())
except FarmadError as err:
    print("order test failed:", err)
    raise
