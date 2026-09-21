"""The coordinator: when it connects, and what it does when it cannot."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from custom_components.hansa_ble import const
from custom_components.hansa_ble.coordinator import HansaCoordinator

from .conftest import ADDRESS, PIN

BLE_DEVICE = "custom_components.hansa_ble.bluetooth.async_ble_device_from_address"
CLEAR_HISTORY = (
    "custom_components.hansa_ble.bluetooth.async_clear_advertisement_history"
)


@pytest.fixture
def coordinator(hass: HomeAssistant, bluetooth_ready: None) -> HansaCoordinator:
    """A coordinator for a faucet named Dusche."""
    return HansaCoordinator(hass, ADDRESS, "Dusche", PIN, 900)


async def test_poll_reads_everything(
    hass: HomeAssistant,
    coordinator: HansaCoordinator,
    mock_client: AsyncMock,
    service_info,
) -> None:
    """One poll fills in readings, counters and settings."""
    with patch(CLEAR_HISTORY) as clear:
        data = await coordinator._async_poll_faucet(service_info)

    assert data.get("location") == "Dusche"
    assert data.get("total_volume") == 9641
    assert data.get("openings") == 38312
    assert data.get("max_run_time") == 60
    assert data.get("valve_open") is False
    assert coordinator.param_a_raw is not None

    # Disconnecting without clearing the history would cost us the next wake-up.
    clear.assert_called_once_with(hass, ADDRESS)
    mock_client.disconnect.assert_awaited()


async def test_needs_poll_respects_the_interval(
    hass: HomeAssistant, coordinator: HansaCoordinator, service_info
) -> None:
    """Between two polls the faucet is left alone."""
    hass.set_state(CoreState.running)
    with patch(BLE_DEVICE, return_value=service_info.device):
        assert coordinator._needs_poll(service_info, None) is True
        assert coordinator._needs_poll(service_info, 60) is False
        assert coordinator._needs_poll(service_info, 901) is True


async def test_needs_poll_without_a_route(
    hass: HomeAssistant, coordinator: HansaCoordinator, service_info
) -> None:
    """No connectable adapter means there is nothing to try."""
    hass.set_state(CoreState.running)
    with patch(BLE_DEVICE, return_value=None):
        assert coordinator._needs_poll(service_info, None) is False


async def test_needs_poll_while_starting(
    hass: HomeAssistant, coordinator: HansaCoordinator, service_info
) -> None:
    """During startup Home Assistant has more urgent things to do."""
    hass.set_state(CoreState.starting)
    with patch(BLE_DEVICE, return_value=service_info.device):
        assert coordinator._needs_poll(service_info, None) is False


async def test_command_authenticates_first(
    hass: HomeAssistant,
    coordinator: HansaCoordinator,
    mock_client: AsyncMock,
    service_info,
) -> None:
    """A command is only written once the faucet accepted the PIN."""
    with patch(BLE_DEVICE, return_value=service_info.device), patch(CLEAR_HISTORY):
        await coordinator.async_send_command(const.CMD_WINK)

    written = [call.args for call in mock_client.write_gatt_char.await_args_list]
    assert written[0][:1] == (const.CH_PASSWORD,)
    assert written[-1][0] == const.CH_COMMAND
    assert written[-1][1] == bytes([const.CMD_WINK])


async def test_command_with_wrong_pin(
    hass: HomeAssistant,
    coordinator: HansaCoordinator,
    mock_client: AsyncMock,
    service_info,
) -> None:
    """A refused PIN asks the user to re-authenticate instead of failing silently."""
    original = mock_client.read_gatt_char.side_effect
    mock_client.read_gatt_char.side_effect = lambda uuid: (
        bytes(16) if uuid == const.CH_NONCE else original(uuid)
    )
    with (
        patch(BLE_DEVICE, return_value=service_info.device),
        patch(CLEAR_HISTORY),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator.async_send_command(const.CMD_WINK)


async def test_command_out_of_range(
    hass: HomeAssistant, coordinator: HansaCoordinator
) -> None:
    """Pressing a button while the faucet sleeps gives a readable error."""
    with patch(BLE_DEVICE, return_value=None), pytest.raises(HomeAssistantError):
        await coordinator.async_send_command(const.CMD_WINK)


async def test_command_write_failure(
    hass: HomeAssistant,
    coordinator: HansaCoordinator,
    mock_client: AsyncMock,
    service_info,
) -> None:
    """A dropped connection mid-command surfaces as an error, not a traceback."""
    mock_client.write_gatt_char.side_effect = [None, OSError("gone")]
    with (
        patch(BLE_DEVICE, return_value=service_info.device),
        patch(CLEAR_HISTORY),
        pytest.raises(HomeAssistantError),
    ):
        await coordinator.async_send_command(const.CMD_WINK)


async def test_set_parameter_preserves_the_block(
    hass: HomeAssistant,
    coordinator: HansaCoordinator,
    mock_client: AsyncMock,
    service_info,
) -> None:
    """Only the addressed field changes; the rest is written back untouched."""
    with patch(BLE_DEVICE, return_value=service_info.device), patch(CLEAR_HISTORY):
        await coordinator.async_set_parameter("max_run_time", 90)

    param_writes = [
        call.args
        for call in mock_client.write_gatt_char.await_args_list
        if call.args[0] == const.CH_PARAM_A
    ]
    assert len(param_writes) == 1
    written = param_writes[0][1]
    assert int.from_bytes(written[10:12], "little") == 90
    assert int.from_bytes(written[0:2], "little") == 1  # untouched neighbour


async def test_set_parameter_failure(
    hass: HomeAssistant,
    coordinator: HansaCoordinator,
    mock_client: AsyncMock,
    service_info,
) -> None:
    """A failed write is reported rather than assumed to have worked."""
    mock_client.write_gatt_char.side_effect = [None, OSError("gone")]
    with (
        patch(BLE_DEVICE, return_value=service_info.device),
        patch(CLEAR_HISTORY),
        pytest.raises(HomeAssistantError),
    ):
        await coordinator.async_set_parameter("max_run_time", 90)


async def test_advertisement_updates_the_battery(
    hass: HomeAssistant,
    coordinator: HansaCoordinator,
    mock_client: AsyncMock,
    service_info,
) -> None:
    """The battery level arrives for free, without connecting."""
    with patch(CLEAR_HISTORY):
        coordinator.data = await coordinator._async_poll_faucet(service_info)

    changed = bytes([0x00, 0x2A, 0x00]) + b"Dusche\x00\x00\x00\x00"
    service_info.manufacturer_data[305] = changed
    coordinator._async_handle_bluetooth_event(service_info, MagicMock())

    assert coordinator.data.get("battery_level") == 42


async def test_set_parameter_with_wrong_pin(
    hass: HomeAssistant,
    coordinator: HansaCoordinator,
    mock_client: AsyncMock,
    service_info,
) -> None:
    """A refused PIN on a write asks for re-authentication too."""
    original = mock_client.read_gatt_char.side_effect
    mock_client.read_gatt_char.side_effect = lambda uuid: (
        bytes(16) if uuid == const.CH_NONCE else original(uuid)
    )
    with (
        patch(BLE_DEVICE, return_value=service_info.device),
        patch(CLEAR_HISTORY),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator.async_set_parameter("max_run_time", 90)
