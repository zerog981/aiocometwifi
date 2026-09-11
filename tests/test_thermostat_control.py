"""Test the commands sent to the thermostat."""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import pytest

from aiocometwifi.exceptions import CometWifiConnectionError, CometWifiError
from aiocometwifi.thermostat import Thermostat

if TYPE_CHECKING:
    from .conftest import FakeTransport

MAC = "AABBCCDDEEFF"
REQUEST_TOPIC = f"01/{MAC}/S/AF"
SETPOINT_TOPIC = f"01/{MAC}/S/A0"
CONFIG_TOPIC = f"01/{MAC}/S/A3"

REQUEST_HEATING = (REQUEST_TOPIC, "#07000000", 0, False)
REQUEST_CONFIG = (REQUEST_TOPIC, "#08000000", 0, False)

Command = Callable[[Thermostat], Awaitable[None]]

CONFIG_COMMANDS: list[tuple[Command, str]] = [
    (Thermostat.enable_key_lock_plus, "#0800000000"),
    (Thermostat.disable_key_lock_plus, "#0008000000"),
    (Thermostat.enable_key_lock, "#0400000000"),
    (Thermostat.disable_key_lock, "#0004000000"),
    (Thermostat.enable_mirrored_display, "#0200000000"),
    (Thermostat.disable_mirrored_display, "#0002000000"),
    (Thermostat.enable_dst, "#0100000000"),
    (Thermostat.disable_dst, "#0001000000"),
]

# Commands requiring the thermostat to be connected
GUARDED_COMMANDS: list[Command] = [
    lambda thermostat: thermostat.set_setpoint_temperature(20.0),
    Thermostat.turn_off,
    Thermostat.turn_fully_on,
    *(command for command, _ in CONFIG_COMMANDS),
]


class TestRequests:
    """Test value requests without considering thermostat replies."""

    async def test_update_values_publishes_the_mask(
        self, thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """The request mask is sent as eight uppercase hex digits."""
        await thermostat.update_values(0x03000000)

        assert transport.published == [(REQUEST_TOPIC, "#03000000", 0, False)]

    async def test_update_config_requests_only_the_config(
        self, thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """A config refresh asks for the config bit alone."""
        await thermostat.update_config()

        assert transport.published == [REQUEST_CONFIG]

    async def test_update_heating_values_requests_the_three_temperatures(
        self, thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """A heating value refresh asks for setpoint, ambient and offset."""
        await thermostat.update_heating_values()

        assert transport.published == [REQUEST_HEATING]


class TestSetpoint:
    """Test the setpoint commands."""

    async def test_set_setpoint_temperature_publishes_then_refreshes(
        self, online_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """Check if setpoint is transmitted followed by a heating refresh."""
        await online_thermostat.set_setpoint_temperature(21.5)

        assert transport.published == [
            (SETPOINT_TOPIC, "#2B", 0, False),
            REQUEST_HEATING,
        ]

    async def test_set_setpoint_temperature_clamps_to_the_maximum(
        self, online_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """Anything above the maximum is sent as the maximum."""
        await online_thermostat.set_setpoint_temperature(35.0)

        assert transport.published[0] == (SETPOINT_TOPIC, "#38", 0, False)

    async def test_set_setpoint_temperature_clamps_to_the_minimum(
        self, online_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """Anything below the minimum is sent as the minimum."""
        await online_thermostat.set_setpoint_temperature(5.0)

        assert transport.published[0] == (SETPOINT_TOPIC, "#10", 0, False)

    async def test_turn_off_sends_the_off_code(
        self, online_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """Turning off writes the off code as the setpoint."""
        await online_thermostat.turn_off()

        assert transport.published == [
            (SETPOINT_TOPIC, "#0F", 0, False),
            REQUEST_HEATING,
        ]

    async def test_turn_fully_on_sends_the_on_code(
        self, online_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """Turning fully on writes the on code as the setpoint."""
        await online_thermostat.turn_fully_on()

        assert transport.published == [
            (SETPOINT_TOPIC, "#39", 0, False),
            REQUEST_HEATING,
        ]


class TestConfiguration:
    """Test the configuration commands."""

    @pytest.mark.parametrize(("command", "payload"), CONFIG_COMMANDS)
    async def test_config_command_publishes_then_refreshes(
        self,
        online_thermostat: Thermostat,
        transport: FakeTransport,
        command: Command,
        payload: str,
    ) -> None:
        """Enable flags sit in the first byte, disable flags in the second."""
        await command(online_thermostat)

        assert transport.published == [
            (CONFIG_TOPIC, payload, 0, False),
            REQUEST_CONFIG,
        ]


class TestNotConnected:
    """Test that commands are refused until the thermostat has answered."""

    @pytest.mark.parametrize("command", GUARDED_COMMANDS)
    async def test_command_raises_before_the_thermostat_answered(
        self,
        connected_thermostat: Thermostat,
        transport: FakeTransport,
        command: Command,
    ) -> None:
        """Subscribed but never answered is not connected."""
        transport.published.clear()

        with pytest.raises(CometWifiConnectionError):
            await command(connected_thermostat)

        assert transport.published == []  # Nothing sent

    async def test_command_raises_after_the_last_will(
        self, online_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """The last will takes the thermostat offline again."""
        transport.deliver(f"01/{MAC}/V/XX", "")

        with pytest.raises(CometWifiConnectionError):
            await online_thermostat.turn_off()

    async def test_connection_error_is_a_library_error(
        self, connected_thermostat: Thermostat
    ) -> None:
        """Callers may catch the base class."""
        with pytest.raises(CometWifiError):
            await connected_thermostat.turn_off()
