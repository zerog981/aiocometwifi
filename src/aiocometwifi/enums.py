"""Enums for thermostat."""

from enum import Enum


class WindowOpenSensitivity(Enum):
    """Sensitivity levels for window open detection sensitivity."""

    LOW = 0b1100
    MEDIUM = 0b1000
    HIGH = 0b0100
