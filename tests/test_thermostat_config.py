"""Test ThermostatConfig dataclass."""

from typing import TYPE_CHECKING

import pytest

from aiocometwifi.const import (
    CFG_DST,
    CFG_KEY_LOCK,
    CFG_KEY_LOCK_PLUS,
    CFG_MIRRORED_DISPLAY,
)
from aiocometwifi.exceptions import CometWifiValueError

if TYPE_CHECKING:
    from aiocometwifi.thermostat import ThermostatConfig


class TestThermostatConfig:
    """Test ThermostatConfig dataclass."""

    def test_config_default_values(self, config: ThermostatConfig) -> None:
        """Config initializes with all False values."""
        assert config.key_lock is False
        assert config.key_lock_plus is False
        assert config.display_mirrored is False
        assert config.dst is False

    def test_write_config_all_combinations(self, config: ThermostatConfig) -> None:
        """Test writing all config byte combinations."""
        for config_byte in range(256):
            config.write_config(config_byte)

            expected_dst = bool(config_byte & CFG_DST)
            expected_mirrored_display = bool(config_byte & CFG_MIRRORED_DISPLAY)
            expected_key_lock = bool(config_byte & CFG_KEY_LOCK)
            expected_key_lock_plus = bool(config_byte & CFG_KEY_LOCK_PLUS)

            assert config.dst is expected_dst, (
                f"Wrong DST value for byte {config_byte:08b}"
            )
            assert config.display_mirrored is expected_mirrored_display, (
                f"Wrong Mirrored Display value for byte {config_byte:08b}"
            )
            assert config.key_lock is expected_key_lock, (
                f"Wrong Key Lock value for byte {config_byte:08b}"
            )
            assert config.key_lock_plus is expected_key_lock_plus, (
                f"Wrong Key Lock Plus value for byte {config_byte:08b}"
            )

    def test_write_config_negative_byte(self, config: ThermostatConfig) -> None:
        """Negative bytes are not allowed."""
        with pytest.raises(CometWifiValueError, match="Invalid configuration byte"):
            config.write_config(-1)

    def test_write_config_larger_input(self, config: ThermostatConfig) -> None:
        """Bits above the low nibble do not disturb the four flags."""
        config.write_config(0xFFFFFF)
        assert config.dst is True
        assert config.display_mirrored is True
        assert config.key_lock is True
        assert config.key_lock_plus is True
