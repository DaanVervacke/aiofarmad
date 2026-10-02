Authentication
==============

The client scripts the same login the web app runs: a PKCE authorization
code against the hosted login form on ``signin.procura.farmad.be``, followed
by a token exchange. The issued access token lives for ten hours and the
refresh token rotates on every use.

Store the token pair and pass it back on the next start. The client refreshes
before the access token expires and calls ``on_token_refresh`` with every
rotated pair. A stored pair logs in without the one-time-code step, because
the refresh token keeps the session alive.

.. code-block:: python

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
