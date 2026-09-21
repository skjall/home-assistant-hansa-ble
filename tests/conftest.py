"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hansa_ble.const import CONF_INTERVAL, CONF_PIN, DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"
SECOND_ADDRESS = "11:22:33:44:55:66"
PIN = "1234"

# Byte 1 is the battery level, bytes 3..12 the installation location.
MANUFACTURER_DATA = bytes([0x00, 0x64, 0x00]) + b"Dusche\x00\x00\x00\x00"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Make the custom integration loadable in every test."""


@pytest.fixture
async def bluetooth_ready(hass, mock_bluetooth: None) -> None:
    """Bring the bluetooth integration up.

    Constructing a coordinator asks the bluetooth manager whether the address
    is present, and without a running integration that manager does not exist.
    """
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "bluetooth", {})
    await hass.async_block_till_done()


@pytest.fixture
def service_info() -> BluetoothServiceInfoBleak:
    """An advertisement as the faucet sends it."""
    device = MagicMock()
    device.address = ADDRESS
    device.name = "ORAS"
    return BluetoothServiceInfoBleak(
        name="ORAS",
        address=ADDRESS,
        rssi=-60,
        manufacturer_data={305: MANUFACTURER_DATA},
        service_data={},
        service_uuids=[],
        source="local",
        device=device,
        advertisement=MagicMock(),
        connectable=True,
        time=0,
        tx_power=-127,
    )


@pytest.fixture
def second_faucet(service_info: BluetoothServiceInfoBleak) -> BluetoothServiceInfoBleak:
    """A second faucet in range, installed somewhere else."""
    device = MagicMock()
    device.address = SECOND_ADDRESS
    device.name = "ORAS"
    return BluetoothServiceInfoBleak(
        name="ORAS",
        address=SECOND_ADDRESS,
        rssi=-70,
        manufacturer_data={
            305: bytes([0x00, 0x50, 0x00]) + b"Bad\x00\x00\x00\x00\x00\x00\x00"
        },
        service_data={},
        service_uuids=[],
        source="local",
        device=device,
        advertisement=MagicMock(),
        connectable=True,
        time=0,
        tx_power=-127,
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A faucet that is already set up."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Dusche",
        unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS, CONF_PIN: PIN},
        options={CONF_INTERVAL: 900},
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """A BleakClient that answers every read with plausible bytes."""
    from custom_components.hansa_ble import const

    # Sixteen zero bytes plus a 0xFF in position 15 means "logged in".
    nonce = bytes(15) + bytes([0xFF])
    answers = {
        const.CH_NONCE: nonce,
        const.CH_PASSWORD: bytes(16),
        const.CH_PRODUCT_INFO: b"1001424\x00\x00" + b"1.30 ",
        const.CH_PRODUCT_NAME: (57162279).to_bytes(4, "little") + b"Waschtisch",
        const.CH_PRODUCT_LOCATION: b"Dusche\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        + b"2104",
        const.CH_STATE_A: bytes([0, 0, 1, 0])
        + (610).to_bytes(2, "little")
        + (100).to_bytes(2, "little")
        + bytes(4)
        + (50).to_bytes(2, "little")
        + bytes(2),
        const.CH_STATE_B: bytes(4)
        + (120).to_bytes(4, "little")
        + (3600).to_bytes(4, "little")
        + (99).to_bytes(4, "little"),
        const.CH_COUNTER_A: (38312).to_bytes(4, "little")
        + bytes(4)
        + (964121).to_bytes(4, "little")
        + (252).to_bytes(4, "little")
        + (7).to_bytes(4, "little"),
        const.CH_COUNTER_B: (9641).to_bytes(4, "little") + bytes(16),
        const.CH_COUNTER_C: bytes(4)
        + (12).to_bytes(4, "little")
        + (500).to_bytes(4, "little"),
        const.CH_PARAM_A: b"".join(
            v.to_bytes(2, "little") for v in (1, 2, 3, 4, 5, 60, 30, 600, 0, 2)
        ),
    }

    client = AsyncMock()
    client.read_gatt_char.side_effect = lambda uuid: answers.get(uuid, bytes(20))
    client.write_gatt_char.return_value = None
    client.disconnect.return_value = None

    with (
        patch(
            "custom_components.hansa_ble.coordinator.establish_connection",
            return_value=client,
        ),
        patch(
            "custom_components.hansa_ble.config_flow.establish_connection",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip the actual setup while testing the flow."""
    with patch(
        "custom_components.hansa_ble.async_setup_entry", return_value=True
    ) as mocked:
        yield mocked
