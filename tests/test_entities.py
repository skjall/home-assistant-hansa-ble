"""What the entities show, and what they do when pressed."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hansa_ble.const import CMD_WINK, DOMAIN

from .conftest import ADDRESS

SCANNER_COUNT = "custom_components.hansa_ble.bluetooth.async_scanner_count"
ADDRESS_PRESENT = "custom_components.hansa_ble.bluetooth.async_address_present"
FALLBACK = (
    "custom_components.hansa_ble.bluetooth.async_set_fallback_availability_interval"
)
CLEAR_HISTORY = (
    "custom_components.hansa_ble.bluetooth.async_clear_advertisement_history"
)


@pytest.fixture
async def set_up_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: AsyncMock
) -> MockConfigEntry:
    """An entry that is set up but has not polled yet."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(SCANNER_COUNT, return_value=1),
        patch(ADDRESS_PRESENT, return_value=True),
        patch(FALLBACK),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, set_up_entry: MockConfigEntry, service_info
) -> MockConfigEntry:
    """An entry that has polled once, so the entities carry values.

    In the field the advertisement comes first and the poll follows from it;
    without that first packet the faucet counts as absent and every entity is
    unavailable, no matter what data a poll produced.
    """
    from unittest.mock import MagicMock

    coordinator = set_up_entry.runtime_data
    with patch(CLEAR_HISTORY):
        data = await coordinator._async_poll_faucet(service_info)
    coordinator.data = data
    coordinator._async_handle_bluetooth_event(service_info, MagicMock())
    await hass.async_block_till_done()
    return set_up_entry


def _entity_id(hass: HomeAssistant, platform: Platform, key: str) -> str:
    """Look entities up by unique id; the slug depends on the active language."""
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{ADDRESS}_{key}"
    )
    assert entity_id is not None, f"{platform}.{key} was never registered"
    return entity_id


async def test_entities_start_unavailable(
    hass: HomeAssistant, set_up_entry: MockConfigEntry
) -> None:
    """Before the first poll there is nothing honest to show."""
    state = hass.states.get(_entity_id(hass, Platform.BINARY_SENSOR, "valve_open"))
    assert state.state == STATE_UNAVAILABLE


async def test_values_after_a_poll(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Once polled, the readings reach the state machine."""
    valve = _entity_id(hass, Platform.BINARY_SENSOR, "valve_open")
    assert hass.states.get(valve).state == STATE_OFF

    volume = _entity_id(hass, Platform.SENSOR, "total_volume")
    assert hass.states.get(volume).state == "9641"

    run_time = _entity_id(hass, Platform.NUMBER, "max_run_time")
    assert hass.states.get(run_time).state == "60"  # a whole number, not "60.0"


async def test_device_is_registered(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """One device per faucet, named after the entry."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, ADDRESS), loaded_entry.entry_id
    )
    assert device is not None
    assert device.name == "Dusche"
    assert device.manufacturer == "Hansa"


async def test_button_sends_its_command(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """Pressing Identify reaches the faucet as the WINK byte."""
    entity_id = _entity_id(hass, Platform.BUTTON, "identify")
    with patch.object(
        loaded_entry.runtime_data, "async_send_command", AsyncMock()
    ) as send:
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    send.assert_awaited_once_with(CMD_WINK)


async def test_number_writes_its_field(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Setting a number writes exactly that productParamA field."""
    entity_id = _entity_id(hass, Platform.NUMBER, "run_on_time")
    with patch.object(
        loaded_entry.runtime_data, "async_set_parameter", AsyncMock()
    ) as write:
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": 5},
            blocking=True,
        )
    write.assert_awaited_once_with("run_on_time", 5)
