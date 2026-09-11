"""Test connecting/disconnecting from the thermostat."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiocometwifi.thermostat import Thermostat

    from .conftest import FakeTransport

MAC = "AABBCCDDEEFF"
PING_TOPIC = f"01/{MAC}/S/XX"
REQUEST_TOPIC = f"01/{MAC}/S/AF"
REPLY_TOPICS = [
    f"01/{MAC}/V/{code}" for code in ("A0", "A1", "A2", "A3", "BD", "A6", "XX")
]


class TestConnect:
    """Test connect()."""

    async def test_connect_subscribes_to_replies_and_ping(
        self, thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """Reply topics and ping topics are subscribed to."""
        await thermostat.connect()
        subscribed = [topic for _, topic, _ in transport.subscribed]
        assert subscribed == [*REPLY_TOPICS, PING_TOPIC]

    async def test_connect_never_subscribes_with_a_wildcard(
        self, thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """Wildcards mix up other thermostat's traffic with this thermostat."""
        await thermostat.connect()
        for _, topic, _ in transport.subscribed:
            assert "+" not in topic
            assert "#" not in topic

    async def test_connect_requests_the_standard_values(
        self, thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """If subscribed the standard values are requested from the thermostat."""
        await thermostat.connect()
        assert transport.published == [(REQUEST_TOPIC, "#7F000E00", 0, False)]


class TestDisconnect:
    """Test disconnect()."""

    async def test_disconnect_releases_every_subscription(
        self, thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """Each subscription made by connect() is released."""
        await thermostat.connect()
        await thermostat.disconnect()
        expected = [{"ticket": n} for n in range(1, len(REPLY_TOPICS) + 2)]
        assert transport.unsubscribed == expected
        assert thermostat.connected is False

    async def test_disconnect_without_connect(
        self, thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """Releasing subscriptions that were never made is not an error."""
        await thermostat.disconnect()
        assert transport.unsubscribed == []
        assert thermostat.connected is False
