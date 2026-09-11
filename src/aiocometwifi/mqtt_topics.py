"""Constructing MQTT topics for communication."""

GROUP_COMMAND = "S"
GROUP_REPLY = "V"
GROUP_TIME = "T"
SEPARATOR = "/"


class MqttTopics:
    """Class for constructing MQTT topics."""

    def __init__(self, mac: str, mode_prefix: str = "01") -> None:
        """Build the command and reply topics of a thermostat.

        :param mac: Streamlined MAC address, e.g., "AABBCCDDEEFF".
        :param mode_prefix: First topic level used by the device.
        """
        topic_structure = mode_prefix + SEPARATOR + mac + SEPARATOR

        # Request topics. Not yet implemented:
        # A5: window open configuration
        # B1: Base software version
        # B2: WiFi software version
        # B3: WiFi signal strength
        command_topic_structure = topic_structure + GROUP_COMMAND + SEPARATOR

        self.command_topics: dict[str, str] = {
            "GENERAL_VALUE_REQUEST": command_topic_structure + "AF",
            "CONNECTION_TEST": command_topic_structure + "XX",
            "WRITE_TEMPERATURE_SETPOINT": command_topic_structure + "A0",
            "WRITE_TEMPERATURE_OFFSET": command_topic_structure + "A2",
            "WRITE_CONFIGURATION": command_topic_structure + "A3",
        }

        reply_topic_structure = topic_structure + GROUP_REPLY + SEPARATOR
        self.reply_topics: dict[str, str] = {
            "TEMPERATURE_SETPOINT": reply_topic_structure + "A0",
            "TEMPERATURE_AMBIENT": reply_topic_structure + "A1",
            "TEMPERATURE_OFFSET": reply_topic_structure + "A2",
            "CONFIGURATION": reply_topic_structure + "A3",
            "KEY_LOCK_PLUS_STATE": reply_topic_structure + "BD",
            "BATTERY": reply_topic_structure + "A6",
            "WILL": reply_topic_structure + "XX",
        }
