"""The config flow, every path through it."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hansa_ble.const import CONF_INTERVAL, CONF_PIN, DOMAIN

from .conftest import ADDRESS, PIN

DISCOVERY = "custom_components.hansa_ble.config_flow.async_discovered_service_info"
BLE_DEVICE = "custom_components.hansa_ble.config_flow.async_ble_device_from_address"


@pytest.fixture
def in_range(service_info):
    """Report one faucet in range, reachable."""
    with (
        patch(DISCOVERY, return_value=[service_info]),
        patch(BLE_DEVICE, return_value=service_info.device),
    ):
        yield


async def test_user_flow(
    hass: HomeAssistant, in_range, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Pick a faucet, enter the PIN, get an entry named after its location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["step_id"] == "pin"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: PIN}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dusche"
    assert result["data"] == {CONF_ADDRESS: ADDRESS, CONF_PIN: PIN}
    assert result["result"].unique_id == ADDRESS


async def test_bluetooth_discovery(
    hass: HomeAssistant,
    service_info,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """A faucet that announces itself goes straight to the PIN step."""
    with patch(BLE_DEVICE, return_value=service_info.device):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pin"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: PIN}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dusche"


async def test_no_devices_found(hass: HomeAssistant) -> None:
    """Nothing in range means nothing to configure."""
    with patch(DISCOVERY, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_already_configured_user(
    hass: HomeAssistant, in_range, mock_config_entry: MockConfigEntry
) -> None:
    """A faucet that is already set up is not offered again."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_already_configured_discovery(
    hass: HomeAssistant, service_info, mock_config_entry: MockConfigEntry
) -> None:
    """Discovery of a known faucet is dropped instead of creating a twin."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("nonce", "expected"),
    [
        (bytes(16), "invalid_pin"),  # byte 15 stays 0, so the PIN was refused
    ],
)
async def test_pin_refused_then_accepted(
    hass: HomeAssistant,
    in_range,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    nonce: bytes,
    expected: str,
) -> None:
    """A wrong PIN shows an error, and the flow recovers from it."""
    from custom_components.hansa_ble import const

    original = mock_client.read_gatt_char.side_effect
    mock_client.read_gatt_char.side_effect = lambda uuid: (
        nonce if uuid == const.CH_NONCE else original(uuid)
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: "9999"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    # Now the right PIN: the very same flow must still be able to finish.
    mock_client.read_gatt_char.side_effect = original
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: PIN}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_cannot_connect_then_recovers(
    hass: HomeAssistant, in_range, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Missing the advertising window is ordinary; trying again must work."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )

    with patch(
        "custom_components.hansa_ble.config_flow.establish_connection",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: PIN}
        )
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: PIN}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_not_in_range(
    hass: HomeAssistant, service_info, mock_setup_entry: AsyncMock
) -> None:
    """No adapter reaches the faucet: say so instead of hanging."""
    with patch(DISCOVERY, return_value=[service_info]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
        with patch(BLE_DEVICE, return_value=None):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_PIN: PIN}
            )
    assert result["errors"] == {"base": "not_in_range"}


async def test_unexpected_error(
    hass: HomeAssistant, in_range, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Anything unforeseen is reported rather than swallowed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    mock_client.read_gatt_char.side_effect = ValueError("boom")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: PIN}
    )
    assert result["errors"] == {"base": "unknown"}


async def test_reauth(
    hass: HomeAssistant,
    in_range,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """A rejected PIN can be replaced without losing the entry."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: "4321"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PIN] == "4321"


async def test_reauth_wrong_pin_recovers(
    hass: HomeAssistant,
    in_range,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Reauth shows the error and still lets the right PIN through."""
    from custom_components.hansa_ble import const

    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    original = mock_client.read_gatt_char.side_effect
    mock_client.read_gatt_char.side_effect = lambda uuid: (
        bytes(16) if uuid == const.CH_NONCE else original(uuid)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: "0000"}
    )
    assert result["errors"] == {"base": "invalid_pin"}

    mock_client.read_gatt_char.side_effect = original
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: PIN}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reconfigure(
    hass: HomeAssistant,
    in_range,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Reconfigure stores a new PIN for the same faucet."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS, CONF_PIN: "5555"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_PIN] == "5555"


async def test_reconfigure_rejects_another_device(
    hass: HomeAssistant,
    service_info,
    second_faucet,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """With two faucets in range, picking the other one must be refused.

    The entry is tied to one device by its unique id; silently repointing it
    would orphan the history of the faucet it used to describe.
    """
    mock_config_entry.add_to_hass(hass)
    with (
        patch(DISCOVERY, return_value=[service_info, second_faucet]),
        patch(BLE_DEVICE, return_value=service_info.device),
    ):
        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: second_faucet.address, CONF_PIN: PIN}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "another_device"


async def test_reconfigure_wrong_pin(
    hass: HomeAssistant,
    in_range,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A PIN the faucet rejects does not get saved."""
    from custom_components.hansa_ble import const

    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    original = mock_client.read_gatt_char.side_effect
    mock_client.read_gatt_char.side_effect = lambda uuid: (
        bytes(16) if uuid == const.CH_NONCE else original(uuid)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS, CONF_PIN: "0000"}
    )
    assert result["errors"] == {"base": "invalid_pin"}
    assert mock_config_entry.data[CONF_PIN] == PIN


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """PIN and interval can be changed after the fact."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_PIN: "7777", CONF_INTERVAL: 1800}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_PIN: "7777", CONF_INTERVAL: 1800}


async def test_title_without_a_location(
    hass: HomeAssistant,
    service_info,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """A faucet with no installation location still gets a usable name."""
    service_info.manufacturer_data[305] = bytes(13)
    with (
        patch(DISCOVERY, return_value=[service_info]),
        patch(BLE_DEVICE, return_value=service_info.device),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: PIN}
        )
    assert result["title"] == "Hansa EEFF"
