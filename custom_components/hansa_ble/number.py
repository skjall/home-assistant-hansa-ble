"""Adjustable timings from productParamA."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HansaConfigEntry
from .coordinator import HansaCoordinator
from .entity import HansaEntity

# Writing means connecting, and the faucet takes one connection at a time.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HansaNumberDescription(NumberEntityDescription):
    """A number and the productParamA field behind it."""

    field: str


NUMBERS: tuple[HansaNumberDescription, ...] = (
    HansaNumberDescription(
        key="max_run_time",
        translation_key="max_run_time",
        field="max_run_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=1,
        native_max_value=600,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    HansaNumberDescription(
        key="manual_flush_time",
        translation_key="manual_flush_time",
        field="manual_flush_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=1,
        native_max_value=600,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    HansaNumberDescription(
        key="cleaning_mode_time",
        translation_key="cleaning_mode_time",
        field="cleaning_mode_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=60,
        native_max_value=1800,
        native_step=10,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    HansaNumberDescription(
        key="run_on_time",
        translation_key="run_on_time",
        field="run_on_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=0,
        native_max_value=60,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HansaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the adjustable timings."""
    async_add_entities(
        HansaNumber(entry.runtime_data, description) for description in NUMBERS
    )


class HansaNumber(HansaEntity, NumberEntity):
    """One writable field of productParamA."""

    entity_description: HansaNumberDescription

    def __init__(
        self, coordinator: HansaCoordinator, description: HansaNumberDescription
    ) -> None:
        """Bind the number to its settings field."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the value as last read from the device."""
        value: float | None = self._value(self.entity_description.field)
        return value

    @property
    def available(self) -> bool:
        """Only offer the setting once we have read the current value."""
        return super().available and self.coordinator.data is not None

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value back to the device."""
        await self.coordinator.async_set_parameter(
            self.entity_description.field, int(value)
        )
