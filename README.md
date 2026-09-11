# aiocometwifi

Async Python library for Eurotronic Comet WiFi radiator thermostats, talking to them over
MQTT through a transport **the caller owns**. The library never opens a connection itself:
hand it the publish, subscribe and unsubscribe functions of your MQTT client, and drive one
`Thermostat` instance per device.

It was written for the Home Assistant integration, whose MQTT integration already owns the
broker connection, but works with any client (the quick start below uses
[paho-mqtt](https://pypi.org/project/paho-mqtt/)).

- Zero runtime dependencies, fully typed (`py.typed`), Python ≥ 3.14.
- Reads setpoint, ambient temperature, offset, battery level and configuration flags.
- Sets the setpoint, turns heating off or fully on, toggles key lock, key lock plus,
  mirrored display and DST.
- Answers the device's connection test so it stays online.

## ✅ Prerequisites

1. **An MQTT broker that accepts anonymous clients** on your LAN (the thermostats do not
support authentication). The official Home Assistant Mosquitto add-on does not qualify.
See [Broker](#-broker).
2. **Each thermostat must be reconfigured for LAN-only operation**, pointing at that broker, using the
   `setup-thermostat` command of `comet-wifi-communicator`. See [Device setup](#-device-setup).
3. **Python ≥ 3.14 and an MQTT client of your own** (paho-mqtt, aiomqtt, Home Assistant's MQTT
   integration, …), the library only adapts to it.

## 📡 Broker

The thermostats connect to an MQTT broker **anonymously** and cannot be given
credentials. Run a broker with `allow_anonymous true`. Restrict what anonymous clients may
access with an ACL (the devices only need `01/#`) and keep the broker off the public internet.
The official Home Assistant Mosquitto add-on refuses anonymous clients by design, so a separate
broker, or a bridge to it, is required.

## 🔧 Device setup

Out of the box a Comet WiFi talks to the manufacturer's cloud. For this library it has to be
reconfigured for **LAN-only** operation, pointed at your own broker. This has to be done once
and with the `setup-thermostat` command of [`comet-wifi-communicator`](https://pypi.org/project/comet-wifi-communicator/):

```bash
pip install comet-wifi-communicator
setup-thermostat --wifi-ssid <ssid> --wifi-password <password> --mqtt-server-ip <broker ip>
```

`aiocometwifi` takes over once the device is on the broker.

## 🚀 Quick start

```python
import asyncio

import paho.mqtt.client as mqtt
from aiocometwifi import MqttClient, SubscribeCallback, SubState, Thermostat


class PahoTransport:
    """Adapt a running paho client to the callables MqttClient expects."""

    def __init__(self, client: mqtt.Client, loop: asyncio.AbstractEventLoop) -> None:
        self._client = client
        self._loop = loop

    async def publish(self, topic: str, payload: str, qos: int, retain: bool) -> None:
        self._client.publish(topic, payload, qos, retain)

    async def subscribe(
        self, sub_state: SubState | None, topic: str, callback: SubscribeCallback
    ) -> SubState:
        def on_message(
            _client: mqtt.Client, _userdata: object, msg: mqtt.MQTTMessage
        ) -> None:
            # paho calls this on its network thread; the library runs on the event loop.
            self._loop.call_soon_threadsafe(callback, msg.topic, msg.payload.decode())

        self._client.message_callback_add(topic, on_message)
        self._client.subscribe(topic)
        return {"topic": topic}

    async def unsubscribe(self, sub_state: SubState) -> None:
        self._client.message_callback_remove(sub_state["topic"])
        self._client.unsubscribe(sub_state["topic"])


async def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect("broker.local")
    client.loop_start()

    transport = PahoTransport(client, asyncio.get_running_loop())
    mqtt_client = MqttClient(
        transport.publish, transport.subscribe, transport.unsubscribe
    )
    thermostat = Thermostat(mqtt_client, "AA:BB:CC:DD:EE:FF")

    await thermostat.connect()  # subscribes; nothing is sent yet
    await thermostat.update_heating_values()
    await asyncio.sleep(5)  # replies arrive asynchronously, see below
    print(thermostat.temperature_ambient, thermostat.setpoint, thermostat.is_heating)

    await thermostat.set_setpoint_temperature(21.0)

    await thermostat.disconnect()
    client.loop_stop()


asyncio.run(main())
```


Requests and replies are separate MQTT messages. `update_*()` publishes a request and returns
immediately; the reply updates the thermostat's properties when it arrives, typically within a
few seconds. Awaiting the reply itself is planned for a later release.

Commands (`set_setpoint_temperature`, `turn_off`, `turn_fully_on`, `enable_*`/`disable_*`) raise
`CometWifiConnectionError` until the device has been heard from. A reply or one of its periodic
connection tests sets `connected`. The device's last will clears it again.

`set_setpoint_temperature` clamps to 8.0–28.0 °C (`TEMPERATURE_SETPOINT_MIN`/`_MAX`) and
truncates to the device's 0.5 °C steps.

## ⚠️ Errors

Everything raised across the API derives from `CometWifiError`:

| Exception | Raised when |
|---|---|
| `CometWifiConnectionError` | A command is issued before the device has answered, or after its last will. |
| `CometWifiValueError` | An argument is rejected (malformed MAC, negative temperature, bad hex). Also a `ValueError`. |
| `CometWifiTimeoutError` | Reserved for awaited replies (later release). |
| `CometWifiInvalidResponseError` | Reserved. Malformed replies are currently logged, not raised. |

Errors from the transport itself (`publish` failing, broker gone) propagate unchanged from
the call that triggered them. One exception is the automatic ping reply, where they are logged.

## 📖 Communication Protocol

Topics are `01/<MAC>/<group>/<code>` with the MAC as twelve uppercase hex digits and the group
`S` for commands (host → device) or `V` for replies (device → host). Payloads are ASCII hex with a
`#` prefix; temperatures are half-degrees (`#2A` = 21.0 °C).

| Topic | Direction | Content |
|---|---|---|
| `S/AF` | Host → Device | Value request, 32-bit mask of what to report |
| `S/A0` | Host → Device | Write setpoint (`#0F` = off, `#39` = fully on) |
| `S/A3` | Host → Device | Write configuration flags |
| `S/XX` | Host ↔ Device | Connection test: the device publishes a ping, the host must answer `#COMM-TEST` on the same topic |
| `V/A0`, `V/A1`, `V/A2` | Host ← Device | Setpoint, ambient temperature, offset |
| `V/A3` | Host ← Device | Configuration (key lock, key lock plus, mirrored display, DST) |
| `V/A6` | Host ← Device | Battery level |
| `V/XX` | Host ← Device | Last will, the device disconnected |

Because the pong goes out on the very topic the library is subscribed to, the broker echoes it
back. The library recognizes its own echoes and rate-limits pongs, so it never loops.

## 🔗 Relation to `comet-wifi-communicator`

[`comet-wifi-communicator`](https://pypi.org/project/comet-wifi-communicator/) is the same
protocol with a bundled paho client, for scripts and standalone use, and it provides the
`setup-thermostat` command above. `aiocometwifi` is for hosts that already have an MQTT
connection and an event loop, Home Assistant first of all.

## 🛠️ Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e . -r requirements_dev.txt
pre-commit install
pytest --cov --cov-fail-under=90 --cov-report=term-missing
ruff check . && ruff format --check . && mypy
```

Tests run against a fake transport (`tests/conftest.py`) so no broker is needed. Commits follow
[Conventional Commits](https://www.conventionalcommits.org/). Releases are cut from `main` by
python-semantic-release.

## ⚖️ Disclaimer

This is an independent, community-developed project. It is not affiliated with, endorsed by or
supported by Eurotronic. *Eurotronic* and *Comet WiFi* are trademarks or trade names of their
respective owners and are used here only to identify the devices this library communicates with.
Use at your own risk. See the license for the warranty disclaimer.

While I am somewhat skeptical towards blindly allowing AI for coding and do not support the way
major companies are selling and training their models, the usefulness for reviewing and improving
software cannot be denied. Therefore, for enhancing the quality of parts of this library and finding issues,
AI (mostly Claude Opus 5) was utilized.

## 📜 License

GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007, see the [license file](LICENSE).
