"""Helper functions."""

import ipaddress
import re


def decode_temperature(hex_value: str) -> float:
    """Convert a hex temperature value to float.
    :param hex_value: Input temperature raw hex value, e.g. "1B".
    :return: Temperature value as decimal number, e.g. 13.5.
    """
    decimal = hex_str_to_int(hex_value)
    return decimal / 2.0


def encode_temperature(decimal: float) -> int:
    """Convert a non-negative temperature value to a raw hex value.
    :param decimal: Input temperature value, e.g. 13.5.
    :return: Temperature value as hex string, e.g. "1B".
    :raises ValueError: If negative temperature is supplied.
    """
    if decimal < 0:
        raise ValueError("Negative temperature.")
    return int(
        decimal * 2.0
    )  # If supplied value is different to .0 or .5, decimals will be cut after doubling


def hex_str_to_int(hex_value: str) -> int:
    """Convert a hex value to int.
    :param hex_value: Raw hex value, e.g. "1B".
    :return: Integer value as decimal number, e.g. 27.
    """
    return int(hex_value, 16)


def int_to_hex_str(number: int, uppercase=False) -> str:
    """Converts an non-negative integer into a string in its hexadecimal representation.
    :param number: Input integer.
    :param uppercase: Convert output letters to uppercase.
    :return:
    """
    if number < 0:
        raise ValueError
    output = format(number, "x")
    if uppercase:
        return output.upper()
    return output


def char_to_unicode(char: str) -> str:
    """Convert a character to its Unicode hex representation.
    :param char: Single character.

    :return: Unicode Hex string.
    :raises ValueError: If multi-character is supplied.
    """
    if len(char) != 1:
        raise ValueError(f"Expected a single character, got {char}.")
    return f"{ord(char):x}"


def string_to_unicode(string: str, uppercase=False) -> str:
    """Convert a string to its Unicode hex representation.
    :param string: Input string.
    :param uppercase: Convert output letters to uppercase.

    :return: Output Unicode hex representation string.
    """
    output = ""
    for char in string:
        output += char_to_unicode(char)
    if uppercase:
        return output.upper()
    return output


def ip_to_hex_str(ip_str: str, uppercase=False) -> str:
    """Converts an IP string into its hex representation.
    :param ip_str: IP address in string format, e.g. "192.168.0.2".
    :param uppercase: Convert output letters to uppercase.
    :return: String of IP in hex representation, e.g. "C0A80002".
    """
    ip = ipaddress.ip_address(ip_str)  # Validate IP
    if ip.version == 6:
        raise IPv6NotAllowed("Supplied IP has IPv6 format. Not supported.")
    ip_hex = ip.packed.hex()
    if uppercase:
        return ip_hex.upper()
    return ip_hex


def validate_and_streamline_mac(mac: str) -> str:
    """Validate and convert a MAC address to a common format.
    :param mac: Input MAC address as string, either delimited by ":" or "-", or as numbers only.
    :return: Streamlined MAC address as string, e.g., AABBCCDDEE.
    :raises: ValueError if MAC address is not valid.
    """
    mac_address_regex = re.compile(
        r"^([0-9a-fA-F]{2}[:-]?){5}([0-9a-fA-F]{2})$|^[0-9a-fA-F]{12}$"
    )
    if not mac_address_regex.match(mac):
        raise ValueError(f"Invalid MAC address: {mac}")
    return mac.replace(":", "").replace("-", "").upper()


class IPv6NotAllowed(Exception):
    """Exception for unsupported IPv6."""
