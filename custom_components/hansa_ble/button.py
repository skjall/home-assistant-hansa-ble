"""Commands sent to the faucet.

Every command authenticates with the PIN first. The factory reset is
deliberately absent - whoever needs it can use the vendor app.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HansaConfigEntry
from .const import CMD_CLEANING, CMD_COUNTER_RESET, CMD_NORMAL, CMD_OPEN, CMD_WINK
from .coordinator import HansaCoordinator
from .entity import HansaEntity

# Each press opens its own connection, and the faucet accepts one at a time.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HansaButtonDescription(ButtonEntityDescription):
    """A button and the byte it writes."""

    command: int


BUTTONS: tuple[HansaButtonDescription, ...] = (
    HansaButtonDescription(
        key="open_valve", translation_key="open_valve", command=CMD_OPEN
    ),
    HansaButtonDescription(
        key="cleaning_mode", translation_key="cleaning_mode", command=CMD_CLEANING
    ),
    HansaButtonDescription(
        key="normal_mode", translation_key="normal_mode", command=CMD_NORMAL
    ),
    HansaButtonDescription(
        key="identify",
        translation_key="identify",
        command=CMD_WINK,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HansaButtonDescription(
        key="reset_counter",
        translation_key="reset_counter",
        command=CMD_COUNTER_RESET,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HansaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the command buttons."""
    async_add_entities(
        HansaButton(entry.runtime_data, description) for description in BUTTONS
    )


class HansaButton(HansaEntity, ButtonEntity):
    """One command byte behind one button."""

    entity_description: HansaButtonDescription

    def __init__(
        self, coordinator: HansaCoordinator, description: HansaButtonDescription
    ) -> None:
        """Bind the button to its command byte."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Send the command."""
        await self.coordinator.async_send_command(self.entity_description.command)
