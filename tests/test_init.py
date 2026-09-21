"""Setting an entry up, and taking it down again."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

SCANNER_COUNT = "custom_components.hansa_ble.bluetooth.async_scanner_count"
ADDRESS_PRESENT = "custom_components.hansa_ble.bluetooth.async_address_present"
FALLBACK = (
    "custom_components.hansa_ble.bluetooth.async_set_fallback_availability_interval"
)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A reachable faucet loads, and unloads cleanly."""
    with (
        patch(SCANNER_COUNT, return_value=1),
        patch(ADDRESS_PRESENT, return_value=True),
        patch(FALLBACK) as fallback,
    ):
        await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # Without this the faucet would be called unavailable between advertisements.
    assert fallback.called

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_without_adapter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """No Bluetooth at all: retry later rather than fail for good."""
    with patch(SCANNER_COUNT, return_value=0):
        await _setup(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_out_of_range(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The faucet may simply be asleep; that is not a permanent error."""
    with (
        patch(SCANNER_COUNT, return_value=1),
        patch(ADDRESS_PRESENT, return_value=False),
    ):
        await _setup(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_options_reload_the_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A changed interval has to reach the coordinator."""
    with (
        patch(SCANNER_COUNT, return_value=1),
        patch(ADDRESS_PRESENT, return_value=True),
        patch(FALLBACK),
    ):
        await _setup(hass, mock_config_entry)
        assert mock_config_entry.runtime_data.interval == 900

        hass.config_entries.async_update_entry(
            mock_config_entry, options={"interval": 1800}
        )
        await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.interval == 1800
