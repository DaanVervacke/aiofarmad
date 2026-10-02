# aiofarmad

[![Check](https://github.com/DaanVervacke/aiofarmad/actions/workflows/check.yml/badge.svg)](https://github.com/DaanVervacke/aiofarmad/actions/workflows/check.yml)
[![PyPI version](https://img.shields.io/pypi/v/aiofarmad.svg)](https://pypi.org/project/aiofarmad/)
[![Python versions](https://img.shields.io/pypi/pyversions/aiofarmad.svg)](https://pypi.org/project/aiofarmad/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Unofficial asynchronous Python library to interact with the Mijn Farmad Apotheek API. Requires Python >= 3.14.

This is a reverse-engineered client and the Farmad API may change or withdraw access without notice. It is not affiliated with or endorsed by Farmad.

## Install

```bash
uv add aiofarmad
```

## Login

```python
import asyncio

from aiofarmad import FarmadClient


async def main() -> None:
    async with FarmadClient(
        email="you@example.com",
        password="your-password",
    ) as client:
        await client.async_login()
        account = await client.async_get_account()
        print(account.full_name, account.entitled_pharmacies)


asyncio.run(main())
```

The login scripts the same authorization-code flow the web app uses: PKCE against the hosted login form on `signin.procura.farmad.be`, then a token exchange for an access token and a rotating refresh token. Accounts with multi-factor authentication pass an otp provider, which the login awaits only when the hosted form demands a one-time code.

```python
async def read_code() -> str:
    return input("code: ")


async with FarmadClient(
    email="you@example.com",
    password="your-password",
    otp_provider=read_code,
) as client:
    await client.async_login()
```

The wait for the code does not count against the request timeout. A rejected code raises `FarmadAuthenticationError`, and a login that needs a code but has no provider raises `FarmadMfaRequiredError`.

## Token persistence

Log in once, store the pair that `async_login` returns, and pass it back on the next start. The client refreshes before the access token expires and calls `on_token_refresh` whenever Farmad rotates the pair.

```python
from aiofarmad import FarmadClient


async def run(stored_access: str, stored_refresh: str) -> None:
    async def save_tokens(access_token: str, refresh_token: str | None) -> None:
        await write_tokens_somewhere(access_token, refresh_token)

    async with FarmadClient(
        access_token=stored_access,
        refresh_token=stored_refresh,
        on_token_refresh=save_tokens,
    ) as client:
        scheme = await client.async_get_medication_day_scheme(
            "343602",
            from_=start_of_today,
            until=end_of_today,
        )
```

## Pharmacists and permissions

Every pharmacy-scoped call takes an apb number, the identifier of one pharmacy. An account only has roles at pharmacies it has been linked to through the app's self-onboarding, which the library exposes as well:

```python
linked = await client.async_link_pharmacy("343602")
```

Calls against a pharmacy the account has no role at raise `FarmadAuthorizationError`.

## Reading data

| Method | Returns |
| --- | --- |
| `async_get_account()` | The account with its pharmacy memberships |
| `async_get_patient()` | The patient record per pharmacy |
| `async_get_organization(apb)` | Public pharmacy information |
| `async_get_pharmacy_preferences(apb)` | What the pharmacy allows for orders |
| `async_get_medication_day_scheme(apb, from_=..., until=...)` | Every intake per day in the window |
| `async_get_medication_nondaily_products(apb, day=...)` | Medications taken outside the daily scheme |
| `async_get_conversations(apb)` | Conversations with the pharmacy |
| `async_get_conversation_messages(apb, customer_account_id)` | Messages in one conversation |
| `async_get_baskets(apb)` | Submitted orders |
| `async_get_draft_basket(apb)` | The current draft basket, or `None` |

## Ordering

Write calls build a draft, submit it, and can cancel a submitted order before the pharmacy processes it:

```python
from aiofarmad import DraftProduct, FarmadClient

products = (DraftProduct(product_cnk="1234567", quantity=1),)

async with FarmadClient(access_token=..., refresh_token=...) as client:
    draft_id = await client.async_save_draft_basket("343602", products=products)
    await client.async_submit_basket(
        "343602",
        draft_id,
        products=products,
        unit_prices=(("1234567", 4.95),),
    )
```

Orders are paid at pickup by default. Most pharmacies do not allow online payments, and asking for one there answers 400. Cancelling a submitted order is the pharmacy's decision: customer accounts regularly get `FarmadAuthorizationError` from `async_cancel_basket`.

## Prescriptions

Prescriptions sit behind the Belgian eHealth platform, and Farmad gates the eHealth session to the browser that completed the itsme consent. Tested against the platform: replaying a live consent session from any non-browser client, with the exact cookies, the exact tokens, and a browser TLS fingerprint, answers 401 every time. No cookie transfer, token pairing, or fingerprint trick carries the session out of the browser.

The library models this honestly:

- `async_get_prescriptions` and `async_get_prescription` carry the verified wire paths.
- Every eHealth call from a non-browser client raises `FarmadEhealthAuthorizationRequiredError`, without burning a refresh token cycle.
- `ehealth_cookie` exists to pass a consent session through, so the library works the day Farmad relaxes the gate. It currently does not open the prescriptions.

Until Farmad changes the platform, prescriptions work in the web app only.

## Errors

| Exception | Meaning |
| --- | --- |
| `FarmadAuthenticationError` | Credentials or tokens were rejected |
| `FarmadMfaRequiredError` | The login needed a one-time code and no otp provider was passed |
| `FarmadAuthorizationError` | The account has no role at this pharmacy |
| `FarmadEhealthAuthorizationRequiredError` | The eHealth consent is missing |
| `FarmadCommunicationError` | The API is unreachable or answered with a failure |
| `FarmadTimeoutError` | A request exceeded the configured timeout |
| `FarmadInvalidResponseError` | A response payload was unusable |
| `FarmadNotFoundError` | The requested object does not exist |
| `FarmadClientClosedError` | The client was closed |

## Development

```bash
uv sync
uv run python -m scripts.check
```

## License

MIT. See [LICENSE](LICENSE).
