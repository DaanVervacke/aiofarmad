Prescriptions
=============

Prescriptions live behind the Belgian eHealth platform. The itsme consent
there runs through a federal login page that requires a real browser, so the
library works with the session that consent creates instead of driving it.

Complete the consent once: open the web app, go to prescriptions, and confirm
with itsme. Then copy the ``Cookie`` request header your browser sends to
``https://procura.farmad.be/ehealth/api/...`` and pass it to the client.

.. code-block:: python

   async with FarmadClient(
       access_token=stored_access,
       refresh_token=stored_refresh,
       ehealth_cookie=".AspNetCore.Cookies=...",
   ) as client:
       prescriptions = await client.async_get_prescriptions()
       one = await client.async_get_prescription("BEP10S18PLM4")

When the cookie is missing or expired, eHealth answers 401 and the client
raises :class:`aiofarmad.FarmadEhealthAuthorizationRequiredError`. Repeat the
consent step to get a fresh cookie. The prescription payloads keep their raw
shape until a consented session is captured.
