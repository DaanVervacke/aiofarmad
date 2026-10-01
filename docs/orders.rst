Orders
======

Order placement builds a draft, submits it, and can cancel a submitted order
before the pharmacy processes it.

.. code-block:: python

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
       baskets = await client.async_get_baskets("343602")
       await client.async_cancel_basket("343602", baskets[-1].id)

Submitting an order is a real transaction with the pharmacy. The pharmacy
sees it, and someone pays or cancels it.
