"""Test the public package surface."""

import aiocometwifi


class TestPublicApi:
    """Everything the integration needs is importable from the package root."""

    def test_all_names_resolve(self) -> None:
        """Every name in __all__ is an attribute of the package."""
        for name in aiocometwifi.__all__:
            assert hasattr(aiocometwifi, name), name

    def test_internals_are_not_exported(self) -> None:
        """Protocol details stay behind the package boundary."""
        internals = ("HEX_PREFIX", "REQUEST_CONFIG", "MqttTopics", "decode_temperature")
        for name in internals:
            assert name not in aiocometwifi.__all__
