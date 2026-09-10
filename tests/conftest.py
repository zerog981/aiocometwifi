"""Shared pytest fixtures."""

import pytest

from aiocometwifi.mqtt import MqttClient, SubscribeCallback, SubState


class FakeTransport:
    """The caller would own the MQTT connection.

    Every call the library makes is recorded, so a test can assert what was sent.
    Each subscription is answered with a state object, so a test can tell which
    subscription a later unsubscribe released.
    """

    def __init__(self) -> None:
        """Start with an empty record."""
        self.published: list[tuple[str, str, int, bool]] = []
        self.subscribed: list[tuple[SubState | None, str, SubscribeCallback]] = []
        self.unsubscribed: list[SubState] = []
        self._issued = 0

    async def publish(
        self,
        topic: str,
        payload: str,
        qos: int,
        retain: bool,  # noqa: FBT001
    ) -> None:
        """Record a published message."""
        self.published.append((topic, payload, qos, retain))

    async def subscribe(
        self, sub_state: SubState | None, topic: str, callback: SubscribeCallback
    ) -> SubState:
        """Record a subscription and hand back a fresh state for it."""
        self.subscribed.append((sub_state, topic, callback))
        self._issued += 1
        return {"ticket": self._issued}

    async def unsubscribe(self, sub_state: SubState) -> None:
        """Record a released subscription state."""
        self.unsubscribed.append(sub_state)


@pytest.fixture
def transport() -> FakeTransport:
    """Return a fake transport."""
    return FakeTransport()


@pytest.fixture
def mqtt_client(transport: FakeTransport) -> MqttClient:
    """Return an MqttClient wired to the fake transport."""
    return MqttClient(transport.publish, transport.subscribe, transport.unsubscribe)
