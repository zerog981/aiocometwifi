"""Helper functions."""

import re

from aiocometwifi.exceptions import CometWifiValueError

_MAC_ADDRESS_REGEX = re.compile(
    r"^([0-9a-fA-F]{2}[:-]?){5}([0-9a-fA-F]{2})$|^[0-9a-fA-F]{12}$"
)


def decode_temperature(hex_value: str) -> float:
    """Convert a hex temperature value to float.

    Returns the temperature value as decimal number, e.g. 13.5.

    :param hex_value: Input temperature raw hex value, e.g. "1B".
    :raises CometWifiValueError: If the value is an invalid hex number.
    """
    return hex_str_to_int(hex_value) / 2.0


def encode_temperature(decimal: float) -> int:
    """Convert a non-negative temperature value to a raw hex value.

    Returns the temperature value as integer, e.g. 27 (hex "1B"). If the supplied
    value has a decimal different to .0 or .5, the value will be cut after doubling.

    :param decimal: Input temperature value, e.g. 13.5.
    :raises CometWifiValueError: If a negative temperature is supplied.
    """
    if decimal < 0:
        msg = "Negative temperature."
        raise CometWifiValueError(msg)
    # If supplied value is different to .0 or .5, decimals will be cut after doubling
    return int(decimal * 2.0)


def hex_str_to_int(hex_value: str) -> int:
    """Convert a hex value to int.

    Returns integer value as decimal number, e.g. 27.

    :param hex_value: Raw hex value, e.g. "1B".
    :raises CometWifiValueError: If the value is not a hex number.
    """
    try:
        return int(hex_value, 16)
    except ValueError as err:
        msg = f"Invalid hex value: {hex_value!r}"
        raise CometWifiValueError(msg) from err


def validate_and_streamline_mac(mac: str) -> str:
    """Validate and convert a MAC address to a common format.

    Returns a streamlined MAC address as string, e.g., AABBCCDDEEFF.

    :param mac: Input MAC address as string, either delimited by ":" or "-",
        or as hex digits only.
    :raises CometWifiValueError: If the MAC address is not valid.
    """
    if not _MAC_ADDRESS_REGEX.match(mac):
        msg = f"Invalid MAC address: {mac}"
        raise CometWifiValueError(msg)
    return mac.replace(":", "").replace("-", "").upper()
