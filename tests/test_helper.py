"""Test helper functions."""

import pytest

from aiocometwifi.exceptions import CometWifiValueError
from aiocometwifi.helper import (
    decode_temperature,
    encode_temperature,
    hex_str_to_int,
    validate_and_streamline_mac,
)


class TestDecodeTemperature:
    """Tests for decoding temperature from thermostats."""

    @pytest.mark.parametrize(
        ("hex_input", "expected_temperature"),
        [
            ("10", 8),
            ("1F", 15.5),
            ("38", 28),
        ],
    )
    def test_basic(self, hex_input: str, expected_temperature: float) -> None:
        """Test basic functionality."""
        assert decode_temperature(hex_input) == expected_temperature

    def test_non_uppercase(self) -> None:
        """Lowercase hex input."""
        assert decode_temperature("1f") == 15.5

    @pytest.mark.parametrize("hex_input", ["GG", "1G", ""])
    def test_invalid(self, hex_input: str) -> None:
        """Invalid hex characters should raise CometWifiValueError."""
        with pytest.raises(CometWifiValueError, match="Invalid hex value"):
            decode_temperature(hex_input)


class TestEncodeTemperature:
    """Tests for encoding temperature for thermostats."""

    @pytest.mark.parametrize(
        ("temperature", "expected"),
        [
            (8, 0x10),
            (15.5, 0x1F),
            (28, 0x38),
            (15.6, 0x1F),  # Cut decimals, if not .5
            (15.9, 0x1F),  # Cut decimals, if not .5
        ],
    )
    def test_basic(self, temperature: float, expected: int) -> None:
        """Test basic functionality."""
        assert encode_temperature(temperature) == expected

    def test_negative(self) -> None:
        """Negative temperatures should raise CometWifiValueError."""
        with pytest.raises(CometWifiValueError, match="Negative temperature"):
            encode_temperature(-10)


class TestHexStrToInt:
    """Tests for hex_str_to_int helper."""

    @pytest.mark.parametrize(
        ("hex_input", "expected"),
        [
            ("1B", 27),
            ("00", 0),
            ("FF", 255),
        ],
    )
    def test_basic(self, hex_input: str, expected: int) -> None:
        """Basic hex input."""
        assert hex_str_to_int(hex_input) == expected

    @pytest.mark.parametrize(("hex_input", "expected"), [("1b", 27), ("Ff", 255)])
    def test_non_uppercase(self, hex_input: str, expected: int) -> None:
        """Lowercase hex input."""
        assert hex_str_to_int(hex_input) == expected

    @pytest.mark.parametrize(
        "hex_input",
        [
            "GG",
            "1G",
            "",
        ],
    )
    def test_invalid_hex(self, hex_input: str) -> None:
        """Invalid hex characters should raise CometWifiValueError."""
        with pytest.raises(CometWifiValueError, match="Invalid hex value"):
            hex_str_to_int(hex_input)


class TestValidateAndStreamlineMac:
    """Tests for validate_and_streamline_mac helper."""

    @pytest.mark.parametrize(
        ("mac", "expected"),
        [
            ("AA:BB:CC:DD:EE:FF", "AABBCCDDEEFF"),
            ("aa:bb:cc:dd:ee:ff", "AABBCCDDEEFF"),
            ("AA-BB-CC-DD-EE-FF", "AABBCCDDEEFF"),
            ("aa-bb-cc-dd-ee-ff", "AABBCCDDEEFF"),
            ("AABBCCDDEEFF", "AABBCCDDEEFF"),
            ("aabbccddeeff", "AABBCCDDEEFF"),
            ("00:00:00:00:00:00", "000000000000"),
            ("FF:FF:FF:FF:FF:FF", "FFFFFFFFFFFF"),
            ("01:23:45:67:89:AB", "0123456789AB"),
            ("a1:b2:c3:d4:e5:f6", "A1B2C3D4E5F6"),
        ],
    )
    def test_valid_mac_formats(self, mac: str, expected: str) -> None:
        """Test valid MAC addresses in all supported formats."""
        assert validate_and_streamline_mac(mac) == expected

    @pytest.mark.parametrize(
        ("mac", "expected"),
        [
            ("aa:bb:cc:dd:ee:ff", "AABBCCDDEEFF"),
            ("AA:BB:CC:DD:EE:FF", "AABBCCDDEEFF"),
            ("Aa:Bb:Cc:Dd:Ee:Ff", "AABBCCDDEEFF"),
            ("aabbccddeeff", "AABBCCDDEEFF"),
            ("AaBbCcDdEeFf", "AABBCCDDEEFF"),
        ],
    )
    def test_case_insensitive(self, mac: str, expected: str) -> None:
        """Test that input case is normalized to uppercase."""
        assert validate_and_streamline_mac(mac) == expected

    @pytest.mark.parametrize(
        "invalid_mac",
        [
            "AA:BB:CC:DD:EE",  # Too few octets
            "AA:BB:CC:DD:EE:FF:00",  # Too many octets
            "GG:BB:CC:DD:EE:FF",  # Invalid hex characters
            "AA:BB:CC:DD:EE:FG",  # Invalid hex character at end
            "AA:BB:CC:DD:EE:",  # Trailing delimiter
            ":AA:BB:CC:DD:EE:FF",  # Leading delimiter
            "AA::BB:CC:DD:EE:FF",  # Double delimiter
            "AABBCCDDEE",  # Too few hex digits (10)
            "AABBCCDDEEFFAA",  # Too many hex digits (14)
            "AA BB CC DD EE FF",  # Space delimiters
            "AA.BB.CC.DD.EE.FF",  # Dot delimiters
            "AA/BB/CC/DD/EE/FF",  # Slash delimiters
            "",  # Empty string
            "ZZZZZZZZZZZZ",  # Invalid hex
            "AA:BB:CC:DD:EE:FF:",  # Trailing colon
            "AA:BB:CC:DD:E:FF",  # Incomplete octet
        ],
    )
    def test_invalid_mac(self, invalid_mac: str) -> None:
        """Test that invalid MAC addresses raise CometWifiValueError."""
        with pytest.raises(CometWifiValueError, match="Invalid MAC address"):
            validate_and_streamline_mac(invalid_mac)

    def test_invalid_mac_is_a_value_error(self) -> None:
        """Callers catching the builtin ValueError keep working."""
        with pytest.raises(ValueError, match="Invalid MAC address"):
            validate_and_streamline_mac("not a mac")
