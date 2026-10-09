Errors
======

Every exception derives from :class:`aiofarmad.FarmadError`, which carries
the HTTP ``status`` when one applies.

.. list-table::
   :header-rows: 1

   * - Exception
     - Parent
     - Meaning
   * - ``FarmadAuthenticationError``
     - ``FarmadError``
     - Credentials or tokens were rejected
   * - ``FarmadMfaRequiredError``
     - ``FarmadAuthenticationError``
     - The login needed a one-time code and no otp provider was passed
   * - ``FarmadMissingIdentifierError``
     - ``FarmadAuthenticationError``
     - No account or patient id was passed and the token carries none
   * - ``FarmadAuthorizationError``
     - ``FarmadError``
     - The account has no role at this pharmacy (403)
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
