"""Test handling of messages from the thermostat."""

import logging
from typing import TYPE_CHECKING

from aiocometwifi.const import TEMPERATURE_SETPOINT_MAX, TEMPERATURE_SETPOINT_MIN

if TYPE_CHECKING:
    import pytest

    from aiocometwifi.thermostat import Thermostat

    from .conftest import FakeTransport

MAC = "AABBCCDDEEFF"
SETPOINT_TOPIC = f"01/{MAC}/V/A0"
AMBIENT_TOPIC = f"01/{MAC}/V/A1"
OFFSET_TOPIC = f"01/{MAC}/V/A2"
CONFIG_TOPIC = f"01/{MAC}/V/A3"
BATTERY_TOPIC = f"01/{MAC}/V/A6"
KEY_LOCK_PLUS_TOPIC = f"01/{MAC}/V/BD"
WILL_TOPIC = f"01/{MAC}/V/XX"


class TestReplies:
    """Test that replies update the thermostat's values."""

    def test_ambient_temperature(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """An ambient temperature reply is decoded from hex half-degrees."""
        transport.deliver(AMBIENT_TOPIC, "#23")

        assert connected_thermostat.temperature_ambient == 17.5

    def test_setpoint_heating(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """A plain setpoint reply sets the setpoint and marks heating on."""
        transport.deliver(SETPOINT_TOPIC, "#28")

        assert connected_thermostat.setpoint == 20.0
        assert connected_thermostat.is_heating is True

    def test_setpoint_off(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """The off code marks heating off and pins the setpoint to the minimum."""
        transport.deliver(SETPOINT_TOPIC, "#28")
        transport.deliver(SETPOINT_TOPIC, "#0F")

        assert connected_thermostat.is_heating is False
        assert connected_thermostat.setpoint == TEMPERATURE_SETPOINT_MIN

    def test_setpoint_fully_on(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """The fully-on code pins the setpoint to the maximum with heating on."""
        transport.deliver(SETPOINT_TOPIC, "#39")

        assert connected_thermostat.setpoint == TEMPERATURE_SETPOINT_MAX
        assert connected_thermostat.is_heating is True

    def test_setpoint_codes_are_case_insensitive(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """A lowercase off code is still the off code."""
        transport.deliver(SETPOINT_TOPIC, "#0f")

        assert connected_thermostat.is_heating is False

    def test_temperature_offset(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """An offset reply is decoded like a temperature."""
        transport.deliver(OFFSET_TOPIC, "#04")

        assert connected_thermostat.temperature_offset == 2.0

    def test_battery_level(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """A battery reply is a plain hex integer."""
        transport.deliver(BATTERY_TOPIC, "#64")

        assert connected_thermostat.battery_level == 100

    def test_configuration(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """The config flags live in the second byte of the reply."""
        transport.deliver(CONFIG_TOPIC, "#0502")

        config = connected_thermostat.config
        assert config.dst is True
        assert config.display_mirrored is False
        assert config.key_lock is True
        assert config.key_lock_plus is False

    def test_untracked_reply_is_ignored(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """A reply we subscribe to but do not track does not do anything."""
        transport.deliver(KEY_LOCK_PLUS_TOPIC, "#01")

        assert connected_thermostat.connected is True


class TestConnected:
    """Test how messages influence the connected flag."""

    def test_any_reply_marks_the_thermostat_connected(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """Hearing from the device means connected."""
        assert connected_thermostat.connected is False

        transport.deliver(AMBIENT_TOPIC, "#23")

        assert connected_thermostat.connected is True

    def test_will_marks_the_thermostat_disconnected(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """The last will means the device disconnected from the broker."""
        transport.deliver(AMBIENT_TOPIC, "#23")

        transport.deliver(WILL_TOPIC, "")

        assert connected_thermostat.connected is False

    async def test_nothing_is_delivered_after_disconnect(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """Once unsubscribed, the transport no longer reaches the thermostat."""
        await connected_thermostat.disconnect()

        transport.deliver(AMBIENT_TOPIC, "#23")

        assert connected_thermostat.temperature_ambient == 0.0


class TestMalformedPayload:
    """Test that a bad payload is dropped, never raised."""

    def test_malformed_payload_is_logged_and_dropped(
        self,
        connected_thermostat: Thermostat,
        transport: FakeTransport,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Garbage on a reply topic leaves the value alone and logs a warning."""
        with caplog.at_level(logging.WARNING, logger="aiocometwifi.thermostat"):
            transport.deliver(AMBIENT_TOPIC, "#ZZ")

        assert connected_thermostat.temperature_ambient == 0.0
        assert "#ZZ" in caplog.text
        assert AMBIENT_TOPIC in caplog.text

    def test_empty_payload_is_logged_and_dropped(
        self,
        connected_thermostat: Thermostat,
        transport: FakeTransport,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A bare prefix with no value is malformed too."""
        with caplog.at_level(logging.WARNING, logger="aiocometwifi.thermostat"):
            transport.deliver(SETPOINT_TOPIC, "#")

        assert connected_thermostat.setpoint == 0.0
        assert "Ignoring malformed payload" in caplog.text
