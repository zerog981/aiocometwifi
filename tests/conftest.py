"""Shared pytest configuration and fixtures."""

from unittest.mock import MagicMock, patch

import pytest
from comet_wifi_communicator.thermostat import Thermostat, ThermostatConfig


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client to avoid real connections."""
    with patch("aiocometwifi.thermostat.Client") as mock:
        yield mock.return_value


@pytest.fixture
def thermostat(mock_mqtt_client):
    """Create a Thermostat instance with mocked MQTT client."""
    return Thermostat(
        mqtt_host="192.168.1.100",
        mqtt_port=1883,
        mac="AA:BB:CC:DD:EE:FF",
    )


@pytest.fixture
def config():
    """Create a ThermostatConfig instance."""
    return ThermostatConfig()


@pytest.fixture
def mock_socket():
    """Patch socket.socket and return the mock instance."""
    mock_socket = MagicMock()
    with patch("aiocometwifi.setup_thermostat.socket.socket", return_value=mock_socket):
        yield mock_socket


@pytest.fixture
def mock_sleep():
    """Patch time.sleep to speed up tests."""
    with patch("aiocometwifi.setup_thermostat.time.sleep"):
        yield


@pytest.fixture
def mock_send_config_data():
    """Fixture that mocks send_config_data function."""
    with patch("aiocometwifi.cli.send_config_data") as mock:
        yield mock
