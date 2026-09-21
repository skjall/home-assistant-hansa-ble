"""Readings and counters of the faucet."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import HansaConfigEntry
from .coordinator import HansaCoordinator
from .entity import HansaEntity

# The coordinator centralises every read.
PARALLEL_UPDATES = 0

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="total_volume",
        translation_key="total_volume",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="openings",
        translation_key="openings",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="open_time",
        translation_key="open_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="auto_flushes",
        translation_key="auto_flushes",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="since_last_use",
        translation_key="since_last_use",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="until_next_flush",
        translation_key="until_next_flush",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="sensor_error",
        translation_key="sensor_error",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HansaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    async_add_entities(
        HansaSensor(entry.runtime_data, description) for description in SENSORS
    )


class HansaSensor(HansaEntity, SensorEntity):
    """A single reading."""

    def __init__(
        self, coordinator: HansaCoordinator, description: SensorEntityDescription
    ) -> None:
        """Bind the sensor to its reading."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        # A device class already supplies the name for the battery sensor.
        if description.translation_key is None:
            self._attr_translation_key = None

    @property
    def native_value(self) -> StateType:
        """Return the current reading."""
        value: StateType = self._value()
        return value

    @property
    def available(self) -> bool:
        """Only report a value once a poll has actually produced one."""
        return super().available and self.coordinator.data is not None
