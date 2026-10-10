Errors
======

Every API, transport, and authentication error derives from
:class:`aiofarmad.FarmadError`, which carries the HTTP ``status`` when one
applies. Invalid arguments, such as an empty apb or a datetime without a
timezone, raise ``ValueError`` before any request is sent.

.. list-table::
   :header-rows: 1

   * - Exception
     - Parent
     - Meaning
   * - ``FarmadAuthenticationError``
     - ``FarmadError``
     - Credentials or tokens are missing or were rejected
   * - ``FarmadMfaRequiredError``
     - ``FarmadAuthenticationError``
     - The login needed a one-time code and no otp provider was passed
   * - ``FarmadMissingIdentifierError``
     - ``FarmadAuthenticationError``
     - No account or patient id was passed and the token carries none
   * - ``FarmadAuthorizationError``
     - ``FarmadError``
     - The pharmacy refused the call (403), usually because the account has no role there
   * - ``FarmadEhealthAuthorizationRequiredError``
     - ``FarmadError``
     - The eHealth consent is missing
   * - ``FarmadCommunicationError``
     - ``FarmadError``
     - The API is unreachable or answered with a failure
   * - ``FarmadTimeoutError``
     - ``FarmadCommunicationError``
     - A request exceeded the configured timeout
   * - ``FarmadInvalidResponseError``
     - ``FarmadCommunicationError``
     - A response payload was unusable
   * - ``FarmadNotFoundError``
     - ``FarmadCommunicationError``
     - The requested object does not exist (404)
   * - ``FarmadClientClosedError``
     - ``FarmadError``
     - The client was closed
