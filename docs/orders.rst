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

Resolving a CNK before you order works through the catalog service:

.. code-block:: python

    product = await client.async_get_product_in_apb("343602", "1234567")
    if product is not None:
        name = product.descriptions.get("nl", "")
        price = product.price.sales_price if product.price else None

The lookup by ``async_get_product_in_apb_by_gtin`` takes the GTIN barcode on
the product box instead of the CNK. Both answer ``None`` when the pharmacy
does not carry the product.
