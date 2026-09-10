"""Test Thermostat initialization."""

import pytest
from comet_wifi_communicator.thermostat import Thermostat


class TestThermostatInit:
    """Test Thermostat initialization."""

    def test_init_sets_correct_attributes(self, mock_mqtt_client, thermostat):
        """MAC is validated, MQTT host/port stored, values initialized."""
        assert thermostat.mac == "AABBCCDDEEFF"
        assert thermostat.mqtt_host == "192.168.1.100"
        assert thermostat.connected is False
        assert thermostat.setpoint == 0.0
        assert thermostat.temperature_ambient == 0.0

    def test_init_registers_mqtt_callbacks(self, mock_mqtt_client):
        """on_connect and on_message callbacks are registered."""
        thermostat = Thermostat("localhost", 1883, "AA:BB:CC:DD:EE:FF")
        assert mock_mqtt_client.on_connect is not None
        assert mock_mqtt_client.on_message is not None

    def test_init_invalid_mac_raises_error(self, mock_mqtt_client):
        """Invalid MAC address raises ValueError."""
        with pytest.raises(ValueError, match="Invalid MAC address"):
            Thermostat("localhost", 1883, "INVALID-MAC")
