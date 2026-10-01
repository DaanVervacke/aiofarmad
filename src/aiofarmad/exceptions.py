"""Exception taxonomy for the Farmad API client."""


class FarmadError(Exception):
    """Base class for every error this library raises."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class FarmadCommunicationError(FarmadError):
    """The Farmad API answered with an unexpected failure or could not be reached."""


class FarmadTimeoutError(FarmadCommunicationError):
    """A Farmad request exceeded the configured timeout."""


class FarmadAuthenticationError(FarmadError):
    """Login failed because the credentials or tokens were rejected."""


class FarmadMfaRequiredError(FarmadAuthenticationError):
    """The account requires multi-factor authentication, which this client cannot complete."""


class FarmadAuthorizationError(FarmadError):
    """The account is not allowed to use this pharmacy feature."""


class FarmadEhealthAuthorizationRequiredError(FarmadError):
    """Prescriptions are unavailable until the eHealth consent is completed."""


class FarmadInvalidResponseError(FarmadCommunicationError):
    """A response carried an unusable payload, such as JSON that is not an object."""


class FarmadNotFoundError(FarmadCommunicationError):
    """A requested object does not exist."""


class FarmadClientClosedError(FarmadError):
    """The client was closed, so no further requests can be made."""
