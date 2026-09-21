"""Valve state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HansaConfigEntry
from .coordinator import HansaCoordinator
from .entity import HansaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HansaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the valve state."""
    async_add_entities([HansaValve(entry.runtime_data)])


class HansaValve(HansaEntity, BinarySensorEntity):
    """Whether water is flowing."""

    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator: HansaCoordinator) -> None:
        """Track whether the valve is open."""
        super().__init__(coordinator, "valve_open")

    @property
    def is_on(self) -> bool | None:
        """Return true while the valve is open."""
        value: bool | None = self._value()
        return value

    @property
    def available(self) -> bool:
        """Only report once a poll has produced a state."""
        return super().available and self.coordinator.data is not None
