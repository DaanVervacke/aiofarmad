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

``async_save_draft_basket`` returns the draft id. ``async_update_draft_basket``
replaces the lines of an existing draft, ``async_clear_draft_basket`` deletes
it, and ``async_get_draft_basket`` reads it back or answers ``None``.

Orders are paid at pickup by default. Most pharmacies do not allow online
payments, and passing ``pay_online=True`` there raises
:class:`aiofarmad.FarmadCommunicationError` with ``status`` 400.
``async_pay_basket`` starts an online payment for a pharmacy that allows it
and returns the raw session the app hands to a browser, because the checkout
runs at the payment provider.

Cancelling a submitted order is the pharmacy's decision. Customer accounts
regularly get :class:`aiofarmad.FarmadAuthorizationError` from
``async_cancel_basket``.

Resolving a CNK before you order works through the catalog service:

.. code-block:: python

    product = await client.async_get_product_in_apb("343602", "1234567")
    if product is not None:
        name = product.descriptions.get("nl", "")
        price = product.price.sales_price if product.price else None

The lookup by ``async_get_product_in_apb_by_gtin`` takes the GTIN barcode on
the product box instead of the CNK. Both answer ``None`` when the pharmacy
does not carry the product.

When only a name is known, the catalog search returns the products of one
pharmacy that match it:

.. code-block:: python

    products = await client.async_search_products_in_apb("343602", "paracetamol")
    for product in products:
        print(product.cnk, product.descriptions.get("nl", ""))

Pages count from 1 and hold at most ``limit`` products, 25 by default. A full
CNK also matches, so the search resolves a product code to its product. A
query without matches answers an empty tuple.

The reimbursement block of the product detail page is a separate read, which
the wire serves without an apb:

.. code-block:: python

    kava = await client.async_get_kava_product("2810901")
    print(kava.is_subject_to_repayment, kava.patient_information_urls.get("nl"))

It carries the repayment and prescription flags and the official patient
information and SPC links per language, in ``patient_information_urls`` and
``summary_of_products_characteristics_urls``.
