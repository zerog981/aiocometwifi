"""Transport interface."""

from collections.abc import Callable, Coroutine
from typing import Any

SubscribeCallback = Callable[[str, str], None]
"""Called with (topic, payload) for each message on a subscribed topic."""

SubState = dict[str, Any]
"""State owned by the caller, content not relevant."""

PublishFn = Callable[[str, str, int, bool], Coroutine[Any, Any, None]]
"""(topic, payload, qos, retain)."""

SubscribeFn = Callable[
    [SubState | None, str, SubscribeCallback], Coroutine[Any, Any, SubState]
]
"""(sub_state, topic, callback), returns the updated state.

sub_state is None on the first subscription to a given topic.
"""

UnsubscribeFn = Callable[[SubState], Coroutine[Any, Any, None]]
"""(sub_state) for a state previously returned by :data:`SubscribeFn."""


class MqttClient:
    """MQTT transport supplied by the caller."""

    def __init__(
        self,
        publish: PublishFn,
        subscribe: SubscribeFn,
        unsubscribe: UnsubscribeFn,
    ) -> None:
        """Store the caller's transport functions.

        :param publish: Publishes a message.
        :param subscribe: Subscribes to one topic and returns its state.
        :param unsubscribe: Releases a subscription state.
        """
        self._publish = publish
        self._subscribe = subscribe
        self._unsubscribe = unsubscribe
        self._substates: dict[tuple[str, str], SubState] = {}

    async def publish(
        self, topic: str, payload: str, *, qos: int = 0, retain: bool = False
    ) -> None:
        """Publish a message.

        :param topic: Topic to publish to.
        :param payload: Message payload.
        :param qos: Quality of service level.
        :param retain: Whether the broker retains the message.
        """
        await self._publish(topic, payload, qos, retain)

    async def subscribe(
        self, unique_id: str, topic: str, callback: SubscribeCallback
    ) -> None:
        """Subscribe to a topic.

        Wildcards must not be used, to avoid receiving messages from other thermostats.

        :param unique_id: Identifies the subscriber.
        :param topic: Topic to subscribe to.
        :param callback: Receives (topic, payload) for each message.
        """
        key = (unique_id, topic)
        self._substates[key] = await self._subscribe(
            self._substates.get(key), topic, callback
        )

    async def unsubscribe(self, unique_id: str, topic: str) -> None:
        """Unsubscribe from a topic.

        :param unique_id: The value passed to meth:`subscribe.
        :param topic: The topic passed to meth:`subscribe.
        """
        substate = self._substates.pop((unique_id, topic), None)
        if substate is None:
            return
        await self._unsubscribe(substate)
