"""Test the MQTT transport interface."""

from typing import TYPE_CHECKING
from unittest.mock import Mock

if TYPE_CHECKING:
    from aiocometwifi.mqtt import MqttClient

    from .conftest import FakeTransport

MAC = "AABBCCDDEEFF"
OTHER_MAC = "112233445566"
PING_TOPIC = f"01/{MAC}/S/XX"
AMBIENT_TOPIC = f"01/{MAC}/V/A1"


class TestPublish:
    """Test publishing a message."""

    async def test_publish_defaults_to_qos_zero_and_no_retain(
        self, mqtt_client: MqttClient, transport: FakeTransport
    ) -> None:
        """A message is unretained at QoS 0 unless asked otherwise."""
        await mqtt_client.publish(PING_TOPIC, "#COMM-TEST")

        assert transport.published == [(PING_TOPIC, "#COMM-TEST", 0, False)]

    async def test_publish_passes_qos_and_retain(
        self, mqtt_client: MqttClient, transport: FakeTransport
    ) -> None:
        """An explicit qos and retain reach the transport unchanged."""
        await mqtt_client.publish(PING_TOPIC, "#COMM-TEST", qos=1, retain=True)

        assert transport.published == [(PING_TOPIC, "#COMM-TEST", 1, True)]


class TestSubscribe:
    """Test subscribing to a topic."""

    async def test_first_subscribe_passes_no_state(
        self, mqtt_client: MqttClient, transport: FakeTransport
    ) -> None:
        """An unknown topic is subscribed with no previous state."""
        callback = Mock()

        await mqtt_client.subscribe(MAC, AMBIENT_TOPIC, callback)

        assert transport.subscribed == [(None, AMBIENT_TOPIC, callback)]

    async def test_repeated_subscribe_passes_the_stored_state(
        self, mqtt_client: MqttClient, transport: FakeTransport
    ) -> None:
        """Subscribing again to a known topic updates it instead of duplicating it."""
        await mqtt_client.subscribe(MAC, AMBIENT_TOPIC, Mock())

        await mqtt_client.subscribe(MAC, AMBIENT_TOPIC, Mock())

        assert transport.subscribed[1][0] == {"ticket": 1}


class TestUnsubscribe:
    """Test unsubscribing from a topic."""

    async def test_unsubscribe_releases_the_matching_state(
        self, mqtt_client: MqttClient, transport: FakeTransport
    ) -> None:
        """The state released is the one belonging to that topic."""
        await mqtt_client.subscribe(MAC, PING_TOPIC, Mock())
        await mqtt_client.subscribe(MAC, AMBIENT_TOPIC, Mock())

        await mqtt_client.unsubscribe(MAC, PING_TOPIC)

        assert transport.unsubscribed == [{"ticket": 1}]

    async def test_unsubscribe_of_unknown_topic_does_nothing(
        self, mqtt_client: MqttClient, transport: FakeTransport
    ) -> None:
        """Tearing down a subscription that was never made is not an error."""
        await mqtt_client.unsubscribe(MAC, PING_TOPIC)

        assert transport.unsubscribed == []

    async def test_unsubscribe_twice_releases_once(
        self, mqtt_client: MqttClient, transport: FakeTransport
    ) -> None:
        """A released subscription is forgotten, so a second call is a no-op."""
        await mqtt_client.subscribe(MAC, PING_TOPIC, Mock())
        await mqtt_client.unsubscribe(MAC, PING_TOPIC)

        await mqtt_client.unsubscribe(MAC, PING_TOPIC)

        assert transport.unsubscribed == [{"ticket": 1}]

    async def test_resubscribe_after_unsubscribe_starts_fresh(
        self, mqtt_client: MqttClient, transport: FakeTransport
    ) -> None:
        """A released topic is unknown again, so it is subscribed from scratch."""
        await mqtt_client.subscribe(MAC, PING_TOPIC, Mock())
        await mqtt_client.unsubscribe(MAC, PING_TOPIC)

        await mqtt_client.subscribe(MAC, PING_TOPIC, Mock())

        assert transport.subscribed[1][0] is None


class TestMultipleDevices:
    """Test that two devices sharing one client stay isolated."""

    async def test_same_topic_under_two_ids_keeps_separate_states(
        self, mqtt_client: MqttClient, transport: FakeTransport
    ) -> None:
        """Two thermostats never share a subscription state."""
        await mqtt_client.subscribe(MAC, PING_TOPIC, Mock())
        await mqtt_client.subscribe(OTHER_MAC, PING_TOPIC, Mock())

        assert transport.subscribed[1][0] is None

        await mqtt_client.unsubscribe(OTHER_MAC, PING_TOPIC)

        assert transport.unsubscribed == [{"ticket": 2}]
