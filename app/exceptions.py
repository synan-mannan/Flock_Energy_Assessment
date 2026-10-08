class PortalError(Exception):
    """Base class for errors communicating with the Urja portal."""


class PortalConfigurationError(PortalError):
    pass


class PortalAuthenticationError(PortalError):
    pass


class PortalNotFoundError(PortalError):
    pass


class PortalUnavailableError(PortalError):
    pass


class PortalTimeoutError(PortalError):
    pass


class UnexpectedPortalResponseError(PortalError):
    pass