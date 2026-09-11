"""Thermostat communication class."""

import asyncio
import logging
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING

from aiocometwifi.const import (
    CFG_DST,
    CFG_KEY_LOCK,
    CFG_KEY_LOCK_PLUS,
    CFG_MIRRORED_DISPLAY,
    CFG_PAYLOAD_LENGTH,
    CONNECTION_TEST_COMMAND,
    CONNECTION_TEST_ECHO_GRACE,
    CONNECTION_TEST_MIN_INTERVAL,
    HEX_PREFIX,
    REQUEST_BASE_SOFTWARE_VERSION,
    REQUEST_BATTERY,
    REQUEST_CONFIG,
    REQUEST_DATETIME,
    REQUEST_TEMPERATURE_AMBIENT,
    REQUEST_TEMPERATURE_OFFSET,
    REQUEST_TEMPERATURE_SETPOINT,
    REQUEST_WIFI_SIGNAL_STRENGTH,
    REQUEST_WIFI_SOFTWARE_VERSION,
    REQUEST_WINDOW_OPEN_CONFIG,
    TEMPERATURE_HEX_OFF,
    TEMPERATURE_HEX_ON,
    TEMPERATURE_SETPOINT_MAX,
    TEMPERATURE_SETPOINT_MIN,
)
from aiocometwifi.enums import WindowOpenSensitivity
from aiocometwifi.exceptions import CometWifiConnectionError, CometWifiValueError
from aiocometwifi.helper import (
    decode_temperature,
    encode_temperature,
    hex_str_to_int,
    validate_and_streamline_mac,
)
from aiocometwifi.mqtt_topics import MqttTopics

if TYPE_CHECKING:
    from aiocometwifi.mqtt import MqttClient

_LOGGER = logging.getLogger(__name__)


@dataclass
class ThermostatData:
    """Holds data for thermostat."""

    temperature_setpoint: float = 0.0
    temperature_ambient: float = 0.0
    temperature_offset: float = 0.0
    window_open: bool = False
    battery_level: float = 0.0
    is_heating: bool = False


@dataclass
class ThermostatConfig:
    """Class for holding thermostat configuration."""

    _key_lock: bool = False
    _key_lock_plus: bool = False
    _display_mirrored: bool = False
    _dst: bool = False

    @property
    def key_lock(self) -> bool:
        """Return key lock status."""
        return self._key_lock

    @property
    def key_lock_plus(self) -> bool:
        """Return key lock plus status."""
        return self._key_lock_plus

    @property
    def display_mirrored(self) -> bool:
        """Return display mirrored status."""
        return self._display_mirrored

    @property
    def dst(self) -> bool:
        """Return daylight savings time (DST) status."""
        return self._dst

    def write_config(self, config_byte: int) -> None:
        """Update configuration from the byte received from thermostat.

        :param config_byte: Configuration byte as received from thermostat.
            Bit 0 is DST, Bit 1 is Mirrored Display, Bit 2 is Key Lock,
            and Bit 3 is Key Lock Plus.
        :raises CometWifiValueError: If the byte is negative.
        """
        if config_byte < 0:
            msg = f"Invalid configuration byte: {config_byte}"
            raise CometWifiValueError(msg)
        self._key_lock_plus = bool(config_byte & CFG_KEY_LOCK_PLUS)
        self._key_lock = bool(config_byte & CFG_KEY_LOCK)
        self._display_mirrored = bool(config_byte & CFG_MIRRORED_DISPLAY)
        self._dst = bool(config_byte & CFG_DST)


@dataclass
class ThermostatWindowOpenConfig:
    """Class for holding thermostat window open configuration."""

    sensitivity: WindowOpenSensitivity = WindowOpenSensitivity.LOW
    off_time: int = 0


class Thermostat:
    """Thermostat communication class.

    :ivar config: Thermostat configuration.

    """

    def __init__(self, mqtt_client: MqttClient, mac: str) -> None:
        """Initialize a thermostat instance.

        :param mqtt_client: MQTT client.
        :param mac: Thermostat MAC Address.
        """
        self._mac = validate_and_streamline_mac(mac)
        self._mqtt = mqtt_client
        self._connected = False
        self._topics = MqttTopics(self._mac)
        # Subscribe to value topics and ping topic
        self._subscriptions = (
            *self._topics.reply_topics.values(),
            self._topics.command_topics["CONNECTION_TEST"],
        )
        self._data = ThermostatData()
        self.config = ThermostatConfig()

        # Ping handling
        self._expected_echoes: list[float] = []
        self._last_pong = float("-inf")
        self._pending: set[asyncio.Task[None]] = set()

    @property
    def connected(self) -> bool:
        """Connection to the thermostat is established."""
        return self._connected

    @property
    def setpoint(self) -> float:
        """Thermostat temperature setpoint."""
        return self._data.temperature_setpoint

    @property
    def temperature_ambient(self) -> float:
        """Ambient temperature as measured by thermostat."""
        return self._data.temperature_ambient

    @property
    def temperature_offset(self) -> float:
        """Temperature offset."""
        return self._data.temperature_offset

    @property
    def is_heating(self) -> bool:
        """True if thermostat is active."""
        return self._data.is_heating

    @property
    def window_open(self) -> bool:
        """True if open window is detected."""
        return self._data.window_open

    @property
    def battery_level(self) -> float:
        """Thermostat battery level."""
        return self._data.battery_level

    @property
    def mac(self) -> str:
        """Thermostat MAC address."""
        return self._mac

    def _on_message(self, topic: str, payload: str) -> None:
        """Handle a message received from the MQTT transport.

        :param topic: Topic of the message.
        :param payload: Message payload, decoded to text.
        """
        # Thermostat connection status
        if topic == self._topics.reply_topics["WILL"]:
            self._connected = False
            return

        if topic == self._topics.command_topics["CONNECTION_TEST"]:
            self._on_ping()
            return
        self._connected = True

        try:
            self._store_reply(topic, payload.lstrip(HEX_PREFIX))
        except ValueError:
            _LOGGER.warning("Ignoring malformed payload %r on %s.", payload, topic)

    def _store_reply(self, topic: str, value: str) -> None:
        """Decode a reply from the thermostat and record it.

        :param topic: Reply topic of value.
        :param value: Payload without hex prefix.
        :raises ValueError: If the value is invalid.
        """
        replies = self._topics.reply_topics
        if topic == replies["TEMPERATURE_AMBIENT"]:
            self._data.temperature_ambient = decode_temperature(value)
        elif topic == replies["TEMPERATURE_SETPOINT"]:
            self._store_setpoint(value)
        elif topic == replies["TEMPERATURE_OFFSET"]:
            self._data.temperature_offset = decode_temperature(value)
        elif topic == replies["BATTERY"]:
            self._data.battery_level = hex_str_to_int(value)
        elif topic == replies["CONFIGURATION"]:
            self.config.write_config(hex_str_to_int(value) >> 8 & 0xFF)

    def _store_setpoint(self, value: str) -> None:
        """Record a setpoint reply, and set off and fully on.

        :param value: Setpoint payload without hex prefix.
        :raises ValueError: If value is invalid.
        """
        raw = hex_str_to_int(value)
        if raw == TEMPERATURE_HEX_OFF:
            self._data.is_heating = False
            self._data.temperature_setpoint = TEMPERATURE_SETPOINT_MIN
            return
        self._data.is_heating = True
        if raw == TEMPERATURE_HEX_ON:
            self._data.temperature_setpoint = TEMPERATURE_SETPOINT_MAX
        else:
            self._data.temperature_setpoint = decode_temperature(value)

    def _require_connected(self) -> None:
        """Refuse a command if the thermostat is not connected.

        :raises CometWifiConnectionError: If no message has arrived from the
        thermostat since the last :meth:`connect` or thermostat has disconnected.
        """
        if not self.connected:
            msg = "Thermostat has not answered."
            raise CometWifiConnectionError(msg)

    def _on_ping(self) -> None:
        """Answer a ping from the thermostat, but ignore echo of broker pong.

        The pong goes out on the same topic the thermostat publishes its ping to
        and the broker replies with the exact same message. Thus, every pong
        sent out is received back as ping. Therefore, an expectation is stored
        when a pong is sent out. The expectation expires after
        CONNECTION_TEST_ECHO_GRACE (a lost echo does not mask a real ping). Further,
        there is a minimum time between sent out pongs to prevent a runaway loop.
        """
        now = monotonic()
        self._expected_echoes = [
            sent
            for sent in self._expected_echoes
            if now - sent < CONNECTION_TEST_ECHO_GRACE
        ]
        if self._expected_echoes:
            self._expected_echoes.pop(0)  # Sent out pong from the broker, the echo
            return

        self._connected = True
        if now - self._last_pong < CONNECTION_TEST_MIN_INTERVAL:
            _LOGGER.warning(
                "Not answering ping from %s: Last pong was %.1f s ago.",
                self._mac,
                now - self._last_pong,
            )
            return

        self._last_pong = now
        self._expected_echoes.append(now)
        task = asyncio.get_running_loop().create_task(self._publish_connection_test())
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _publish_connection_test(self) -> None:
        """Publish a pong."""
        try:
            await self._mqtt.publish(
                self._topics.command_topics["CONNECTION_TEST"], CONNECTION_TEST_COMMAND
            )
        except Exception:
            _LOGGER.exception("Could not answer ping from %s.", self._mac)

    async def connect(self) -> None:
        """Subscribe to thermostat topics and request standard values."""
        for topic in self._subscriptions:
            await self._mqtt.subscribe(self._mac, topic, self._on_message)
        await self.update_standard_values()

    async def disconnect(self) -> None:
        """Release the subscriptions done by :meth:`connect`."""
        for task in self._pending:
            task.cancel()
        for topic in self._subscriptions:
            await self._mqtt.unsubscribe(self._mac, topic)
        self._expected_echoes.clear()
        self._connected = False

    async def update_values(self, request_value: int = 0xFFFFFFFF) -> None:
        """Request parameters.

        Fetches setpoint temperature, ambient temperature, battery level,
        configuration parameters, open window settings etc.

        :param request_value: Supply requested values as
        REQUEST_TEMPERATURE_SETPOINT | REQUEST_TEMPERATURE_AMBIENT |
        REQUEST_WIFI_SIGNAL_STRENGTH.

        """
        request_str = f"{HEX_PREFIX}{request_value:08X}"
        await self._mqtt.publish(
            self._topics.command_topics["GENERAL_VALUE_REQUEST"], request_str
        )

    async def update_standard_values(self) -> None:
        """Query thermostat for standard parameters.

        Fetches setpoint temperature, ambient temperature, temperature offset,
        configuration, datetime, window open configuration, battery level, base
        software version, wifi software version, and wifi signal strength.

        """
        await self.update_values(
            REQUEST_TEMPERATURE_SETPOINT
            | REQUEST_TEMPERATURE_AMBIENT
            | REQUEST_TEMPERATURE_OFFSET
            | REQUEST_CONFIG
            | REQUEST_DATETIME
            | REQUEST_WINDOW_OPEN_CONFIG
            | REQUEST_BATTERY
            | REQUEST_BASE_SOFTWARE_VERSION
            | REQUEST_WIFI_SOFTWARE_VERSION
            | REQUEST_WIFI_SIGNAL_STRENGTH
        )

    async def update_heating_values(self) -> None:
        """Query thermostat for heating-relevant parameters.

        Fetches setpoint temperature, ambient temperature, and temperature offset.

        """
        await self.update_values(
            REQUEST_TEMPERATURE_SETPOINT
            | REQUEST_TEMPERATURE_AMBIENT
            | REQUEST_TEMPERATURE_OFFSET
        )
        # Window open detection is not implemented yet, but should be requested later.

    async def update_config(self) -> None:
        """Query thermostat for configuration.

        Fetches configuration from thermostat.

        """
        await self.update_values(REQUEST_CONFIG)

    async def _config_enable(self, values: int = 0x0000) -> None:
        """Enable a config setting.

        :param values: Flags of config parameters to enable.
        """
        self._require_connected()
        # Payload has five bytes with first byte containing enable flags
        config_payload = (
            f"{HEX_PREFIX}{values:02X}{'0' * ((CFG_PAYLOAD_LENGTH - 1) * 2)}"
        )
        await self._mqtt.publish(
            self._topics.command_topics["WRITE_CONFIGURATION"], config_payload
        )
        await self.update_config()

    async def _config_disable(self, values: int = 0x0000) -> None:
        """Disable a config setting.

        :param values: Flags of config parameters to disable.
        """
        self._require_connected()
        # Payload has five bytes with second byte containing disable flags
        config_payload = (
            f"{HEX_PREFIX}{'0' * 2}{values:02X}{'0' * ((CFG_PAYLOAD_LENGTH - 2) * 2)}"
        )
        await self._mqtt.publish(
            self._topics.command_topics["WRITE_CONFIGURATION"], config_payload
        )
        await self.update_config()

    async def enable_key_lock_plus(self) -> None:
        """Enable key lock plus.

        Activates key lock that can only be controlled remotly
        and not directly on the device.

        """
        await self._config_enable(CFG_KEY_LOCK_PLUS)

    async def disable_key_lock_plus(self) -> None:
        """Disable key lock plus.

        Disable key lock that can only be controlled remotly and not
        directly on the device.

        """
        await self._config_disable(CFG_KEY_LOCK_PLUS)

    async def enable_key_lock(self) -> None:
        """Enable key lock.

        This key lock may also be disabled directly on the device.

        """
        await self._config_enable(CFG_KEY_LOCK)

    async def disable_key_lock(self) -> None:
        """Disable key lock.

        This key lock may also be disabled directly on the device.

        """
        await self._config_disable(CFG_KEY_LOCK)

    async def enable_mirrored_display(self) -> None:
        """Enable mirrored display.

        Rotate device display by 180 degrees.

        """
        await self._config_enable(CFG_MIRRORED_DISPLAY)

    async def disable_mirrored_display(self) -> None:
        """Disable mirrored display.

        Set device display rotation back to default.

        """
        await self._config_disable(CFG_MIRRORED_DISPLAY)

    async def enable_dst(self) -> None:
        """Enable daylight savings time.

        Enable daylight savings time (DST) for device clock.

        """
        await self._config_enable(CFG_DST)

    async def disable_dst(self) -> None:
        """Disable daylight savings time.

        Disable daylight savings time (DST) for device clock.

        """
        await self._config_disable(CFG_DST)

    async def set_setpoint_temperature(self, temperature: float) -> None:
        """Set thermostat setpoint temperature.

        :param temperature: Setpoint temperature.

        """
        self._require_connected()
        temperature = min(temperature, TEMPERATURE_SETPOINT_MAX)
        temperature = max(temperature, TEMPERATURE_SETPOINT_MIN)
        temperature_encoded = f"{HEX_PREFIX}{encode_temperature(temperature):02X}"
        await self._mqtt.publish(
            self._topics.command_topics["WRITE_TEMPERATURE_SETPOINT"],
            temperature_encoded,
        )
        await self.update_heating_values()

    async def turn_off(self) -> None:
        """Turn thermostat off.

        Disable thermostat heating. Frost protection may stay enabled.
        """
        self._require_connected()
        await self._mqtt.publish(
            self._topics.command_topics["WRITE_TEMPERATURE_SETPOINT"],
            f"{HEX_PREFIX}{TEMPERATURE_HEX_OFF:02X}",
        )
        await self.update_heating_values()

    async def turn_fully_on(self) -> None:
        """Turn thermostat fully on.

        Set thermostat to be fully open (unregulated heating).
        """
        self._require_connected()
        await self._mqtt.publish(
            self._topics.command_topics["WRITE_TEMPERATURE_SETPOINT"],
            f"{HEX_PREFIX}{TEMPERATURE_HEX_ON:02X}",
        )
        await self.update_heating_values()
