"""Test ThermostatData dataclass."""

from aiocometwifi.thermostat import ThermostatData


class TestThermostatData:
    """Test ThermostatData dataclass."""

    def test_default_values(self) -> None:
        """Initialization with all standard values."""
        data = ThermostatData()

        assert data.temperature_setpoint == 0.0
        assert data.temperature_ambient == 0.0
        assert data.temperature_offset == 0.0
        assert data.window_open is False
        assert data.battery_level == 0.0
        assert data.is_heating is False
