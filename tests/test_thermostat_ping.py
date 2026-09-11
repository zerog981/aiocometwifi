"""Test answering the thermostat's pings without answering our own echo."""

import asyncio
import logging
from typing import TYPE_CHECKING

import pytest

from aiocometwifi.const import CONNECTION_TEST_ECHO_GRACE, CONNECTION_TEST_MIN_INTERVAL

if TYPE_CHECKING:
    from aiocometwifi.thermostat import Thermostat

    from .conftest import FakeTransport

MAC = "AABBCCDDEEFF"
PING_TOPIC = f"01/{MAC}/S/XX"
AMBIENT_TOPIC = f"01/{MAC}/V/A1"
WILL_TOPIC = f"01/{MAC}/V/XX"
COMM_TEST = "#COMM-TEST"
PONG = (PING_TOPIC, COMM_TEST, 0, False)


class FakeClock:
    """A monotonic clock the test moves by hand."""

    def __init__(self) -> None:
        """Start at an arbitrary, non-zero instant."""
        self.now = 1000.0

    def __call__(self) -> float:
        """Return the current fake time."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward."""
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """Replace the thermostat module's clock with a fake."""
    fake = FakeClock()
    monkeypatch.setattr("aiocometwifi.thermostat.monotonic", fake)
    return fake


async def receive(transport: FakeTransport, topic: str, payload: str) -> None:
    """Deliver a message and let the loop run any pong it scheduled."""
    transport.deliver(topic, payload)
    await asyncio.sleep(0)


@pytest.mark.usefixtures("clock")
class TestPong:
    """Test that a genuine ping is answered."""

    @pytest.mark.usefixtures("online_thermostat")
    async def test_ping_is_answered_once_and_unretained(
        self, transport: FakeTransport
    ) -> None:
        """A ping gets exactly one pong, at QoS 0 and never retained."""
        await receive(transport, PING_TOPIC, COMM_TEST)

        assert transport.published == [PONG]

    async def test_ping_marks_the_thermostat_connected(
        self, connected_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """A ping means the thermostat is connected."""
        await receive(transport, PING_TOPIC, COMM_TEST)

        assert connected_thermostat.connected is True

    @pytest.mark.usefixtures("online_thermostat")
    async def test_pings_far_apart_are_each_answered(
        self, transport: FakeTransport, clock: FakeClock
    ) -> None:
        """Ping, echo, ten minutes later ping, echo: two pongs."""
        await receive(transport, PING_TOPIC, COMM_TEST)
        await receive(transport, PING_TOPIC, COMM_TEST)  # echo
        clock.advance(600)

        await receive(transport, PING_TOPIC, COMM_TEST)
        await receive(transport, PING_TOPIC, COMM_TEST)  # echo

        assert transport.published == [PONG, PONG]


@pytest.mark.usefixtures("clock")
class TestEcho:
    """Test that our own pong, echoed by the broker, is not answered."""

    @pytest.mark.usefixtures("online_thermostat")
    async def test_echo_is_not_answered(self, transport: FakeTransport) -> None:
        """The message right after our pong is our pong."""
        await receive(transport, PING_TOPIC, COMM_TEST)

        await receive(transport, PING_TOPIC, COMM_TEST)  # echo

        assert transport.published == [PONG]

    async def test_echo_does_not_mark_the_thermostat_connected(
        self, online_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """An echo is us, not the thermostat, so it cannot undo a last will."""
        await receive(transport, PING_TOPIC, COMM_TEST)
        await receive(transport, WILL_TOPIC, "")

        await receive(transport, PING_TOPIC, COMM_TEST)  # echo

        assert online_thermostat.connected is False

    @pytest.mark.usefixtures("online_thermostat")
    async def test_lost_echo_does_not_swallow_the_next_ping(
        self, transport: FakeTransport, clock: FakeClock
    ) -> None:
        """An expectation expires after the grace period."""
        await receive(transport, PING_TOPIC, COMM_TEST)
        # the echo never arrives
        clock.advance(600)

        await receive(transport, PING_TOPIC, COMM_TEST)

        assert transport.published == [PONG, PONG]

    @pytest.mark.usefixtures("online_thermostat")
    async def test_echo_within_grace_is_still_recognised(
        self, transport: FakeTransport, clock: FakeClock
    ) -> None:
        """A slow echo just inside the grace period is the one send by the broker."""
        await receive(transport, PING_TOPIC, COMM_TEST)
        clock.advance(CONNECTION_TEST_ECHO_GRACE / 2)

        await receive(transport, PING_TOPIC, COMM_TEST)  # slow echo

        assert transport.published == [PONG]


@pytest.mark.usefixtures("clock")
class TestRunawayGuard:
    """Test the rate floor that stops a reply loop."""

    @pytest.mark.usefixtures("online_thermostat")
    async def test_flood_of_pings_gets_one_pong_per_interval(
        self,
        transport: FakeTransport,
        clock: FakeClock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Pings arriving faster than the floor are answered once, and logged."""
        with caplog.at_level(logging.WARNING, logger="aiocometwifi.thermostat"):
            for _ in range(5):
                clock.advance(
                    CONNECTION_TEST_ECHO_GRACE + 1
                )  # past the echo window each time
                await receive(transport, PING_TOPIC, COMM_TEST)

        assert transport.published == [PONG]
        assert "Not answering ping" in caplog.text

    @pytest.mark.usefixtures("online_thermostat")
    async def test_ping_after_the_interval_is_answered_again(
        self, transport: FakeTransport, clock: FakeClock
    ) -> None:
        """Once the floor has passed, the next ping gets its pong."""
        await receive(transport, PING_TOPIC, COMM_TEST)
        clock.advance(CONNECTION_TEST_MIN_INTERVAL)

        await receive(transport, PING_TOPIC, COMM_TEST)

        assert transport.published == [PONG, PONG]


@pytest.mark.usefixtures("clock")
class TestFailures:
    """Test that the pong never raises into the transport."""

    @pytest.mark.usefixtures("online_thermostat")
    async def test_failed_pong_is_logged_not_raised(
        self,
        transport: FakeTransport,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A transport error while answering is logged with its traceback."""
        transport.publish_error = RuntimeError("broker gone")

        with caplog.at_level(logging.ERROR, logger="aiocometwifi.thermostat"):
            await receive(transport, PING_TOPIC, COMM_TEST)

        assert transport.published == []
        assert "Could not answer ping" in caplog.text
        assert "broker gone" in caplog.text

    async def test_disconnect_cancels_a_pending_pong(
        self, online_thermostat: Thermostat, transport: FakeTransport
    ) -> None:
        """A pong scheduled but not yet sent is dropped on disconnect."""
        transport.deliver(PING_TOPIC, COMM_TEST)  # scheduled, loop not run yet

        await online_thermostat.disconnect()
        await asyncio.sleep(0)

        assert transport.published == []
