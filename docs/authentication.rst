Authentication
==============

The client scripts the same login the web app runs: a PKCE authorization
code against the hosted login form on ``signin.procura.farmad.be``, followed
by a token exchange. The issued access token lives for ten hours and the
refresh token rotates on every use.

Store the token pair and pass it back on the next start. The client refreshes
before the access token expires and calls ``on_token_refresh`` with every
rotated pair.

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

Accounts with multi-factor authentication cannot complete this flow. The
login raises :class:`aiofarmad.FarmadMfaRequiredError` for them.
