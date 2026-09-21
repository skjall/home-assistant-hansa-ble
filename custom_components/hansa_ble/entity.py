"""Shared base: every entity hangs off the same device."""

from __future__ import annotations

from typing import Any

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo

from .const import DOMAIN, MANUFACTURER
from .coordinator import HansaCoordinator


class HansaEntity(PassiveBluetoothCoordinatorEntity[HansaCoordinator]):
    """Base entity for the faucet."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HansaCoordinator, key: str) -> None:
        """Tie this entity to one faucet and one reading."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_translation_key = key

    @property
    def device_info(self) -> DeviceInfo:
        """One device per faucet, named by whatever the entry is called."""
        data = self.coordinator.data
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, self.coordinator.address)},
            manufacturer=MANUFACTURER,
            model=data.get("product_name") if data else None,
            name=self.coordinator.device_name,
            hw_version=str(data.get("hardware_version")) if data else None,
            serial_number=str(data.get("serial_number")) if data else None,
        )

    def _value(self, key: str | None = None) -> Any:
        """Return one reading, or None while nothing has been read yet."""
        data = self.coordinator.data
        return data.get(key or self._key) if data else None
