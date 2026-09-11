"""Exceptions raised by this library.

Everything raised across the API boundary derives from :class:`CometWifiError`.
"""


class CometWifiError(Exception):
    """Base class for every error raised by this library."""


class CometWifiConnectionError(CometWifiError):
    """The thermostat is unreachable.

    Raised when the device has not answered, or has announced its own
    disconnect through its last will. Broker problems are not reported here.
    """


class CometWifiTimeoutError(CometWifiError):
    """A request was published but no reply arrived in time."""


class CometWifiInvalidResponseError(CometWifiError):
    """A reply from the thermostat could not be parsed."""


class CometWifiValueError(CometWifiError, ValueError):
    """An argument was rejected, such as a malformed MAC address.

    Also, a :class:`ValueError`, so callers that already catch that keep
    working.
    """
