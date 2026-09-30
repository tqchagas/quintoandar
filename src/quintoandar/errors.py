class QuintoAndarError(RuntimeError):
    """Base class for client errors."""


class PortalBlocked(QuintoAndarError):
    """The portal rejected or rate-limited a request; callers should stop."""


class RequestFailed(QuintoAndarError):
    """The portal returned an unsuccessful or malformed response."""


class EstimateUnavailable(QuintoAndarError):
    """The valuation endpoint did not return a price for the supplied input."""


class ListingNotFound(QuintoAndarError):
    """The portal does not have a price suggestion for this listing id."""
