"""Hansa/Oras BLE faucet."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    AVAILABILITY_INTERVAL,
    CONF_INTERVAL,
    CONF_PIN,
    DEFAULT_INTERVAL,
    DOMAIN,
)
from .coordinator import HansaCoordinator

type HansaConfigEntry = ConfigEntry[HansaCoordinator]

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: HansaConfigEntry) -> bool:
    """Set up a faucet from a config entry."""
    address = entry.data[CONF_ADDRESS]

    if not bluetooth.async_scanner_count(hass, connectable=True):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="no_scanner"
        )
    if not bluetooth.async_address_present(hass, address, connectable=True):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="not_in_range",
            translation_placeholders={"address": address},
        )

    # The faucet is silent between advertisements. Without this it would be
    # declared unavailable long before it has actually gone away.
    bluetooth.async_set_fallback_availability_interval(
        hass, address, AVAILABILITY_INTERVAL
    )

    coordinator = HansaCoordinator(
        hass,
        address,
        entry.title,
        entry.options.get(CONF_PIN, entry.data.get(CONF_PIN, "")),
        entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL),
    )
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Only start once every platform has had its chance to subscribe.
    entry.async_on_unload(coordinator.async_start())
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: HansaConfigEntry) -> None:
    """Reload so the new PIN and interval take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HansaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
