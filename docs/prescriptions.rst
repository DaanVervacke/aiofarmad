Prescriptions
=============

Prescriptions live behind the Belgian eHealth platform, and Farmad gates the
eHealth session to the browser that completed the itsme consent. Replaying a
live consent session from a non-browser client, with the exact cookies, the
exact tokens, and a browser TLS fingerprint, answers 401 every time. The
session cannot be carried out of the browser by cookies alone.

The library models this honestly. ``async_get_prescriptions`` and
``async_get_prescription`` carry the verified wire paths, and every eHealth call from a non-browser client
raises :class:`aiofarmad.FarmadEhealthAuthorizationRequiredError` without
burning a refresh token cycle. The ``ehealth_cookie`` argument exists to pass
a consent session through, so the library works the day Farmad relaxes the
gate. It currently does not open the prescriptions.

Until Farmad changes the platform, prescriptions work in the web app only.
