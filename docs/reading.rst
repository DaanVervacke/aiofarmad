Reading data
============

Every read below takes the apb number of one pharmacy where the signature
shows ``apb``. Reads that take an optional ``patient_id`` or ``account_id``
default to the values the access token carries.

.. list-table::
   :header-rows: 1

   * - Method
     - Returns
   * - ``async_get_account()``
     - The account with its pharmacy memberships
   * - ``async_get_patient()``
     - The patient record per pharmacy
   * - ``async_get_organization(apb)``
     - Public pharmacy information
   * - ``async_get_pharmacy_preferences(apb)``
     - What the pharmacy allows for orders
   * - ``async_get_medication_day_scheme(apb, from_=..., until=...)``
     - Every intake per day in the window
   * - ``async_get_medication_nondaily_products(apb, day=...)``
     - Medications taken outside the daily scheme
   * - ``async_get_medication_scheme_for_product(apb, cnk)``
     - The scheme entries of one product for the patient
   * - ``async_get_conversations(apb)``
     - Conversations with the pharmacy
   * - ``async_get_conversation_messages(apb, customer_account_id)``
     - Messages in one conversation
   * - ``async_get_product_in_apb(apb, cnk)``
     - One product by its CNK at one pharmacy, or ``None``
   * - ``async_get_product_in_apb_by_gtin(apb, gtin)``
     - One product by its GTIN barcode at one pharmacy, or ``None``
   * - ``async_search_products_in_apb(apb, query)``
     - The products at one pharmacy matching a search term
   * - ``async_get_kava_product(cnk)``
     - The reimbursement data and official patient links of one product
   * - ``async_get_baskets(apb)``
     - Submitted orders
   * - ``async_get_draft_basket(apb)``
     - The current draft basket, or ``None``
   * - ``async_get_service_messages()``
     - Platform banners outside the pharmacy data
   * - ``async_has_technical_interruptions()``
     - Whether the Farmad platform reports an interruption

The medication reads and the catalog search take a ``language`` argument
that defaults to ``"nl"``. The conversation reads page through ``limit`` and
``page`` with the first page at 0. The catalog search uses the same
arguments with the first page at 1. The basket read pages through ``skip``
and ``take``.
