"""Test Thermostat initialization."""

from typing import TYPE_CHECKING

import pytest

from aiocometwifi.exceptions import CometWifiValueError
from aiocometwifi.thermostat import Thermostat

if TYPE_CHECKING:
    from aiocometwifi.mqtt import MqttClient

    from .conftest import FakeTransport


class TestThermostatInit:
    """Test Thermostat initialization."""

    def test_init_sets_correct_attributes(self, thermostat: Thermostat) -> None:
        """MAC is normalized, nothing connected, values empty."""
        assert thermostat.mac == "AABBCCDDEEFF"
        assert thermostat.connected is False
        assert thermostat.setpoint == 0.0
        assert thermostat.temperature_ambient == 0.0

    def test_init_leaves_the_transport_untouched(
        self, transport: FakeTransport
    ) -> None:
        """Nothing subscribed/published before connect."""
        assert transport.subscribed == []
        assert transport.published == []

    def test_init_invalid_mac_raises_error(self, mqtt_client: MqttClient) -> None:
        """Invalid MAC address raises CometWifiValueError."""
        with pytest.raises(CometWifiValueError, match="Invalid MAC address"):
            Thermostat(mqtt_client, "INVALID-MAC")
