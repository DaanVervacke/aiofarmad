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
when you select it, and store the apb number it returns.

.. code-block:: python

   linked = await client.async_link_pharmacy("343602")

Reads that need a patient id or an account id default to the values the
access token carries.
