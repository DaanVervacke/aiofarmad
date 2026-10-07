Quickstart
==========

Install the package, then create a client with your Mijn Farmad credentials.

.. code-block:: python

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

Every pharmacy-scoped call needs the apb number of one pharmacy. The account
only has roles at pharmacies it has been linked to. Call
``async_link_pharmacy`` once for your pharmacy, the same step the app runs
when you select it, and keep the apb number you passed for later calls.

.. code-block:: python

   linked = await client.async_link_pharmacy("343602")

The call returns ``True`` on success. A refused link raises instead of
returning ``False``.

Reads that need a patient id or an account id default to the
``patient_id`` and ``account_id`` properties, which come from the access
token. When neither is available the call raises
:class:`aiofarmad.FarmadAuthenticationError`.

``FarmadClient`` takes an optional ``aiohttp.ClientSession`` as its first
argument. An injected session stays owned by the caller, and the client
closes only a session it created. ``request_timeout`` sets the per-request
timeout in seconds and defaults to 30. Use the client as an async context
manager or call ``async_close`` when done.

Accounts with multi-factor authentication pass an otp provider to the
client. The login awaits it only when the hosted form demands a one-time
code.

.. code-block:: python

   async def read_code() -> str:
       return input("code: ")


   client = FarmadClient(
       email="you@example.com",
       password="your-password",
       otp_provider=read_code,
   )
