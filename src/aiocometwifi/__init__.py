"""Async library for Comet WiFi thermostats over a caller-supplied MQTT transport.

The caller owns the MQTT connection and hands its publish, subscribe and
unsubscribe functions to :class:`MqttClient`. One :class:`Thermostat` per
device then talks to the corresponding device.
"""

from aiocometwifi.const import TEMPERATURE_SETPOINT_MAX, TEMPERATURE_SETPOINT_MIN
from aiocometwifi.exceptions import (
    CometWifiConnectionError,
    CometWifiError,
    CometWifiInvalidResponseError,
    CometWifiTimeoutError,
    CometWifiValueError,
)
from aiocometwifi.mqtt import (
    MqttClient,
    PublishFn,
    SubscribeCallback,
    SubscribeFn,
    SubState,
    UnsubscribeFn,
)
from aiocometwifi.thermostat import Thermostat, ThermostatConfig, ThermostatData

__all__ = [
    "TEMPERATURE_SETPOINT_MAX",
    "TEMPERATURE_SETPOINT_MIN",
    "CometWifiConnectionError",
    "CometWifiError",
    "CometWifiInvalidResponseError",
    "CometWifiTimeoutError",
    "CometWifiValueError",
    "MqttClient",
    "PublishFn",
    "SubState",
    "SubscribeCallback",
    "SubscribeFn",
    "Thermostat",
    "ThermostatConfig",
    "ThermostatData",
    "UnsubscribeFn",
]
