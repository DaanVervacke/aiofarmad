API reference
=============

Client
------

.. autoclass:: aiofarmad.FarmadClient
   :members:
   :undoc-members:

.. autodata:: aiofarmad.TokenRefreshCallback

Models
------

.. autoclass:: aiofarmad.FarmadAccount
   :members:
.. autoclass:: aiofarmad.AccountMembership
   :members:
.. autoclass:: aiofarmad.FarmadPatient
   :members:
.. autoclass:: aiofarmad.PatientInPharmacy
   :members:
.. autoclass:: aiofarmad.Pharmacy
   :members:
.. autoclass:: aiofarmad.PharmacyPreferences
   :members:
.. autoclass:: aiofarmad.MedicationDayScheme
   :members:
.. autoclass:: aiofarmad.MedicationIntakeMoment
   :members:
.. autoclass:: aiofarmad.MedicationSchemeProduct
   :members:
.. autoclass:: aiofarmad.MedicationNondailyProduct
   :members:
.. autoclass:: aiofarmad.MedicationSchemeProductEntry
   :members:
.. autoclass:: aiofarmad.MedicationTemporality
   :members:
.. autoclass:: aiofarmad.ConversationSummary
   :members:
.. autoclass:: aiofarmad.FarmadMessage
   :members:
.. autoclass:: aiofarmad.MessageDraft
   :members:
.. autoclass:: aiofarmad.MessageDraftAttachment
   :members:
.. autoclass:: aiofarmad.MessageDraftAttachmentVariant
   :members:
.. autoclass:: aiofarmad.ServiceMessage
   :members:
.. autoclass:: aiofarmad.CatalogProduct
   :members:
.. autoclass:: aiofarmad.CatalogProductCode
   :members:
.. autoclass:: aiofarmad.CatalogProductPrice
   :members:
.. autoclass:: aiofarmad.CatalogProductStock
   :members:
.. autoclass:: aiofarmad.KavaProduct
   :members:
.. autoclass:: aiofarmad.CustomerBasket
   :members:
.. autoclass:: aiofarmad.BasketLine
   :members:
.. autoclass:: aiofarmad.BasketItem
   :members:
.. autoclass:: aiofarmad.BasketPayment
   :members:
.. autoclass:: aiofarmad.DraftBasket
   :members:
.. autoclass:: aiofarmad.DraftProduct
   :members:
.. autoclass:: aiofarmad.FarmadTokens
   :members:
.. autoclass:: aiofarmad.Prescription
   :members:

Exceptions
----------

.. autoclass:: aiofarmad.FarmadError
.. autoclass:: aiofarmad.FarmadCommunicationError
.. autoclass:: aiofarmad.FarmadTimeoutError
.. autoclass:: aiofarmad.FarmadAuthenticationError
.. autoclass:: aiofarmad.FarmadMfaRequiredError
.. autoclass:: aiofarmad.FarmadAuthorizationError
.. autoclass:: aiofarmad.FarmadEhealthAuthorizationRequiredError
.. autoclass:: aiofarmad.FarmadInvalidResponseError
.. autoclass:: aiofarmad.FarmadNotFoundError
.. autoclass:: aiofarmad.FarmadClientClosedError
