"""Test MQTT message reception and parsing."""

import time
from unittest.mock import Mock, patch

import pytest
from comet_wifi_communicator.const import (
    CONNECTION_TEST_TIMEOUT,
    HEX_PREFIX,
    TEMPERATURE_HEX_OFF,
    TEMPERATURE_HEX_ON,
    TEMPERATURE_SETPOINT_MAX,
    TEMPERATURE_SETPOINT_MIN,
)


class TestMqttMessageHandling:
    """Test MQTT message reception and parsing."""

    def test_on_message_will_sets_disconnected(self, thermostat):
        """Receipt of WILL message sets connected=False."""
        thermostat._connected = True
        mock_message = Mock()
        mock_message.topic = thermostat._topics.reply_topics["WILL"]

        thermostat._on_mqtt_message(None, None, mock_message)

        assert thermostat.connected is False

    def test_on_message_ambient_temperature(self, thermostat):
        """Ambient temperature message updates internal value."""
        mock_message = Mock()
        mock_message.topic = thermostat._topics.reply_topics["TEMPERATURE_AMBIENT"]
        mock_message.payload.decode.return_value = "#23"

        thermostat._on_mqtt_message(None, None, mock_message)

        assert thermostat.temperature_ambient == 17.5

    def test_on_message_configuration(self, thermostat):
        """Configuration message updates internal value."""
        mock_message = Mock()
        mock_message.topic = thermostat._topics.reply_topics["CONFIGURATION"]
        mock_message.payload.decode.return_value = "#0502"

        thermostat._on_mqtt_message(None, None, mock_message)

        assert thermostat.config.dst is True
        assert thermostat.config.display_mirrored is False
        assert thermostat.config.key_lock is True
        assert thermostat.config.key_lock_plus is False

    def test_on_message_setpoint_heating(self, thermostat):
        """Heating setpoint temperature updates value and heating status."""
        mock_message = Mock()
        mock_message.topic = thermostat._topics.reply_topics["TEMPERATURE_SETPOINT"]
        mock_message.payload.decode.return_value = "#28"

        thermostat._on_mqtt_message(None, None, mock_message)

        assert thermostat.setpoint == 20.0
        assert thermostat.is_heating is True

    def test_on_message_setpoint_off(self, thermostat):
        """OFF setpoint sets is_heating=False and setpoint to MIN."""
        mock_message = Mock()
        mock_message.topic = thermostat._topics.reply_topics["TEMPERATURE_SETPOINT"]
        mock_message.payload.decode.return_value = (
            f"{HEX_PREFIX}{TEMPERATURE_HEX_OFF:02X}"
        )

        thermostat._on_mqtt_message(None, None, mock_message)

        assert thermostat.is_heating is False
        assert thermostat.setpoint == TEMPERATURE_SETPOINT_MIN

    def test_on_message_setpoint_fully_on(self, thermostat):
        """Setpoint for fully open thermostat sets setpoint to MAX and is_heating=True."""
        mock_message = Mock()
        mock_message.topic = thermostat._topics.reply_topics["TEMPERATURE_SETPOINT"]
        mock_message.payload.decode.return_value = (
            f"{HEX_PREFIX}{TEMPERATURE_HEX_ON:02X}"
        )

        thermostat._on_mqtt_message(None, None, mock_message)

        assert thermostat.setpoint == TEMPERATURE_SETPOINT_MAX
        assert thermostat.is_heating is True

    # def test_on_message_battery_level(self, thermostat):
    #     """Battery message updates battery_level."""
    #     mock_message = Mock()
    #     mock_message.topic = thermostat._topics.reply_topics["BATTERY"]
    #     mock_message.payload.decode.return_value = "#64"
    #
    #     thermostat._on_mqtt_message(None, None, mock_message)
    #
    #     assert thermostat.battery_level == 100

    def test_on_message_connection_test_timeout_not_exceeded(self, thermostat):
        """Test if connection test when timeout is not exceeded is ignored."""
        thermostat._last_connection_test_published = time.time()
        mock_message = Mock()
        mock_message.topic = thermostat._topics.command_topics["CONNECTION_TEST"]

        with patch.object(thermostat, "_publish_connection_test") as mock_publish:
            thermostat._on_mqtt_message(None, None, mock_message)
            mock_publish.assert_not_called()

    def test_on_message_connection_test_timeout_exceeded(self, thermostat):
        """Connection test when timeout exceeded publishes response."""
        thermostat._last_connection_test_published = time.time() - (
            CONNECTION_TEST_TIMEOUT + 1
        )
        thermostat._connected = False
        mock_message = Mock()
        mock_message.topic = thermostat._topics.command_topics["CONNECTION_TEST"]

        with patch.object(thermostat, "_publish_connection_test") as mock_publish:
            thermostat._on_mqtt_message(None, None, mock_message)
            mock_publish.assert_called_once()
            assert thermostat.connected is True


class TestPublishing:
    """Test outgoing MQTT messages."""

    def test_publish_connection_test(self, thermostat, mock_mqtt_client):
        """Connection test publishes and updates time of last connection test."""
        with patch("time.time", return_value=1000.0):
            thermostat._publish_connection_test()

        mock_mqtt_client.publish.assert_called_once()
        assert thermostat._last_connection_test_published == 1000.0

    @pytest.mark.asyncio
    async def test_update_values_publishes_request(self, thermostat, mock_mqtt_client):
        """update_values publishes formatted hex request."""
        request_value = 0x03000000
        await thermostat.update_values(request_value)

        mock_mqtt_client.publish.assert_called()
        call_args = mock_mqtt_client.publish.call_args
        assert "#03000000" in call_args[0][1]
