"""Shared pytest fixtures."""

import pytest

from aiocometwifi.mqtt import MqttClient, SubscribeCallback, SubState
from aiocometwifi.thermostat import Thermostat


class FakeTransport:
    """The caller would own the MQTT connection.

    Every call the library makes is recorded, so a test can assert what was sent.
    Each subscription is answered with a state object, so a test can tell which
    subscription a later unsubscribe released. :meth:`deliver` plays the broker
    and hands a message to whichever callback is subscribed to its topic.
    """

    def __init__(self) -> None:
        """Start with an empty record."""
        self.published: list[tuple[str, str, int, bool]] = []
        self.subscribed: list[tuple[SubState | None, str, SubscribeCallback]] = []
        self.unsubscribed: list[SubState] = []
        self._issued = 0
        self._callbacks: dict[str, SubscribeCallback] = {}
        self._topic_of_ticket: dict[int, str] = {}
        self.publish_error: Exception | None = None

    async def publish(
        self,
        topic: str,
        payload: str,
        qos: int,
        retain: bool,  # noqa: FBT001
    ) -> None:
        """Record a published message, or fail if instructed."""
        if self.publish_error is not None:
            raise self.publish_error
        self.published.append((topic, payload, qos, retain))

    async def subscribe(
        self, sub_state: SubState | None, topic: str, callback: SubscribeCallback
    ) -> SubState:
        """Record a subscription and hand back a fresh state for it."""
        self.subscribed.append((sub_state, topic, callback))
        self._issued += 1
        self._callbacks[topic] = callback
        self._topic_of_ticket[self._issued] = topic
        return {"ticket": self._issued}

    async def unsubscribe(self, sub_state: SubState) -> None:
        """Record a released subscription state and stop delivering to it."""
        self.unsubscribed.append(sub_state)
        topic = self._topic_of_ticket.pop(sub_state["ticket"])
        self._callbacks.pop(topic, None)

    def deliver(self, topic: str, payload: str) -> None:
        """Hand a message to the callback subscribed to its topic."""
        callback = self._callbacks.get(topic)
        if callback is not None:
            callback(topic, payload)


@pytest.fixture
def transport() -> FakeTransport:
    """Return a fake transport."""
    return FakeTransport()


@pytest.fixture
def mqtt_client(transport: FakeTransport) -> MqttClient:
    """Return an MqttClient wired to the fake transport."""
    return MqttClient(transport.publish, transport.subscribe, transport.unsubscribe)


@pytest.fixture
def thermostat(mqtt_client: MqttClient) -> Thermostat:
    """Return a thermostat with fake transport."""
    return Thermostat(mqtt_client, "AA:BB:CC:DD:EE:FF")


@pytest.fixture
async def connected_thermostat(thermostat: Thermostat) -> Thermostat:
    """Return a thermostat with subscriptions in place."""
    await thermostat.connect()
    return thermostat


@pytest.fixture
def online_thermostat(
    connected_thermostat: Thermostat, transport: FakeTransport
) -> Thermostat:
    """Return a thermostat that has answered."""
    transport.deliver("01/AABBCCDDEEFF/V/A1", "#23")  # Temperature ambient
    transport.published.clear()
    return connected_thermostat
