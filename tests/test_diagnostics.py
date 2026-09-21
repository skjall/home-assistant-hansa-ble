"""Diagnostics, and what they must not contain."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import PIN

SCANNER_COUNT = "custom_components.hansa_ble.bluetooth.async_scanner_count"
ADDRESS_PRESENT = "custom_components.hansa_ble.bluetooth.async_address_present"
FALLBACK = (
    "custom_components.hansa_ble.bluetooth.async_set_fallback_availability_interval"
)


async def test_diagnostics_redact_the_pin(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Diagnostics get shared in bug reports; the PIN must not travel with them."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(SCANNER_COUNT, return_value=1),
        patch(ADDRESS_PRESENT, return_value=True),
        patch(FALLBACK),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert PIN not in str(result)
    assert result["entry"]["data"]["pin"] == "**REDACTED**"
    assert result["entry"]["data"]["address"] == "**REDACTED**"
    assert "coordinator" in result
    assert result["coordinator"]["interval"] == 900
