Authentication
==============

The client scripts the same login the web app runs: a PKCE authorization
code against the hosted login form on ``signin.procura.farmad.be``, followed
by a token exchange. The issued access token lives for ten hours and the
refresh token rotates on every use.

``async_login`` returns a :class:`aiofarmad.FarmadTokens`. Store its
``access_token`` and ``refresh_token`` and pass them back on the next start.
The client refreshes 30 seconds before the access token expires, retries a
request once after a 401 when it holds a refresh token, and calls
``on_token_refresh`` after a login and after every rotation. The client logs
an exception raised by the callback and does not raise it again, so a failed
save leaves the stored pair stale while the client keeps working. A stored pair logs in
without the one-time-code step, because the refresh token keeps the session
alive.

.. code-block:: python

   from datetime import UTC, datetime, timedelta

   start_of_today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
   end_of_today = start_of_today + timedelta(days=1)


   async def save_tokens(access_token: str, refresh_token: str | None) -> None:
       await write_tokens_somewhere(access_token, refresh_token)


   async with FarmadClient(
       access_token=stored_access,
       refresh_token=stored_refresh,
       on_token_refresh=save_tokens,
   ) as client:
       scheme = await client.async_get_medication_day_scheme(
           "343602", from_=start_of_today, until=end_of_today
       )

Accounts with multi-factor authentication pass an otp provider. The login
awaits it only when the hosted form demands a one-time code, and the wait
does not count against the request timeout.

.. code-block:: python

   async def read_code() -> str:
       return input("code: ")


   async with FarmadClient(
       email="you@example.com",
       password="your-password",
       otp_provider=read_code,
   ) as client:
       await client.async_login()

A rejected code raises :class:`aiofarmad.FarmadAuthenticationError`. A login
that needs a code without a provider raises
:class:`aiofarmad.FarmadMfaRequiredError`.
