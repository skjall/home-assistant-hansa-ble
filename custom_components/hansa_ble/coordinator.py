"""Talking to the faucet.

The device advertises for a short moment every few minutes and is connectable
only during that window, so polling on a timer would mostly hit a device that
is not listening. Instead every advertisement asks whether a poll is due, and
the poll runs while we know the faucet is awake.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import hansa_ble_protocol as protocol
from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from .const import (
    CH_COMMAND,
    CH_COUNTER_A,
    CH_COUNTER_B,
    CH_COUNTER_C,
    CH_NONCE,
    CH_PARAM_A,
    CH_PASSWORD,
    CH_PRODUCT_INFO,
    CH_PRODUCT_LOCATION,
    CH_PRODUCT_NAME,
    CH_STATE_A,
    CH_STATE_B,
    DOMAIN,
    MANUFACTURER_ID,
)

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

_LOGGER = logging.getLogger(__name__)

# Reading every characteristic takes a handful of round trips; anything less
# than this and BlueZ has not even finished resolving services yet.
_CONNECT_TIMEOUT = 20.0

# Four connection attempts at _CONNECT_TIMEOUT each, plus the dozen reads that
# follow, fit inside this. A GATT read that never returns does not, and that is
# the point: nothing may outlive the poll it belongs to. Bleak puts no deadline
# of its own on a read, so a sleeping faucet that never drops the link would
# otherwise hold the lock until Home Assistant restarts.
_POLL_TIMEOUT = 120.0

# Hanging up is best effort - by then the faucet is asleep either way.
_DISCONNECT_TIMEOUT = 10.0

_READERS: tuple[tuple[str, Any], ...] = (
    (CH_PRODUCT_INFO, protocol.parse_product_info),
    (CH_PRODUCT_NAME, protocol.parse_product_name),
    (CH_PRODUCT_LOCATION, protocol.parse_product_location),
    (CH_STATE_A, protocol.parse_state_a),
    (CH_STATE_B, protocol.parse_state_b),
    (CH_COUNTER_A, protocol.parse_counter_a),
    (CH_COUNTER_B, protocol.parse_counter_b),
    (CH_COUNTER_C, protocol.parse_counter_c),
)


class HansaCoordinator(ActiveBluetoothDataUpdateCoordinator[protocol.FaucetData]):
    """Poll the faucet whenever it tells us it is awake."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        device_name: str,
        pin: str,
        interval: int,
    ) -> None:
        """Set up the coordinator for one faucet."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            address=address,
            needs_poll_method=self._needs_poll,
            poll_method=self._async_poll_faucet,
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=True,
        )
        self.device_name = device_name
        self._pin = pin
        self.interval = interval
        self._lock = asyncio.Lock()
        self.param_a_raw: bytes | None = None

    @callback
    def _needs_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        seconds_since_last_poll: float | None,
    ) -> bool:
        """Decide, on every advertisement, whether to connect."""
        if (
            seconds_since_last_poll is not None
            and seconds_since_last_poll < self.interval
        ):
            return False
        return self.hass.state is CoreState.running and bool(
            bluetooth.async_ble_device_from_address(
                self.hass, service_info.device.address, connectable=True
            )
        )

    def _ble_device(self) -> BLEDevice:
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="not_in_range",
                translation_placeholders={"address": self.address},
            )
        return device

    async def _async_connect(self, device: BLEDevice) -> BleakClient:
        # A BleakClient is never reused across connections; doing so makes
        # connecting markedly less reliable.
        return await establish_connection(
            BleakClient,
            device,
            self.address,
            max_attempts=4,
            timeout=_CONNECT_TIMEOUT,
        )

    @callback
    def _after_disconnect(self) -> None:
        """Let the next identical advertisement through again.

        The Bluetooth manager drops advertisements that are byte for byte the
        same as the previous one. The faucet's "I am awake" packet rarely
        changes, so without this the next wake-up would never reach us.

        Which makes a failed connection the worst moment to skip it. No
        advertisement reaches the coordinator, so nothing asks for a poll, so
        nothing tries again: one refused connection and the faucet stays
        unavailable until the entry is reloaded. Observed in the field, for
        four hours, with the device advertising at -50 dBm the whole time.
        """
        bluetooth.async_clear_advertisement_history(self.hass, self.address)

    async def _async_disconnect(self, client: BleakClient | None) -> None:
        """Hang up, then let the next advertisement through.

        A disconnect that never returns holds the lock just as surely as a
        hanging read, so it gets a deadline of its own - and the history is
        cleared however this ended, including when there is no client at all
        because connecting is what failed. That case is the one that strands
        the integration: see `_after_disconnect`.
        """
        try:
            if client is not None:
                async with asyncio.timeout(_DISCONNECT_TIMEOUT):
                    await client.disconnect()
        except (TimeoutError, BleakError) as err:
            _LOGGER.debug("%s: disconnecting failed: %s", self.address, err)
        finally:
            self._after_disconnect()

    async def _async_authenticate(self, client: BleakClient) -> None:
        """Challenge-response. Only writes need it; reading works without."""
        nonce = bytes(await client.read_gatt_char(CH_NONCE))
        password = bytes(await client.read_gatt_char(CH_PASSWORD))
        await client.write_gatt_char(
            CH_PASSWORD,
            protocol.auth_response(nonce, password, self._pin),
            response=True,
        )
        if not protocol.is_authenticated(bytes(await client.read_gatt_char(CH_NONCE))):
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_pin"
            )

    async def _async_read_all(self, client: BleakClient) -> protocol.FaucetData:
        """Read every characteristic over an open connection."""
        values: dict[str, Any] = {}
        for uuid, parse in _READERS:
            values.update(parse(bytes(await client.read_gatt_char(uuid))))
        self.param_a_raw = bytes(await client.read_gatt_char(CH_PARAM_A))
        values.update(protocol.parse_param_a(self.param_a_raw))
        return protocol.FaucetData(values)

    async def _async_poll_faucet(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> protocol.FaucetData:
        """Read every characteristic while the faucet is awake.

        The deadline covers acquiring the lock as well. Home Assistant only
        counts a poll as failed when it raises, so a poll that hangs instead
        leaves the coordinator reporting its last success for ever, and every
        later poll queues up behind the lock. That is silent: no error, no
        retry, no entity that admits to being stale.
        """
        async with asyncio.timeout(_POLL_TIMEOUT), self._lock:
            client: BleakClient | None = None
            try:
                client = await self._async_connect(service_info.device)
                return await self._async_read_all(client)
            finally:
                await self._async_disconnect(client)

    @callback
    def _async_store(self, data: protocol.FaucetData) -> None:
        """Record a reading taken outside the poll loop.

        A command reads everything back over the same connection, so it proves
        the device answers just as a poll does. Saying so keeps the entities
        from staying unavailable after an earlier poll failed.
        """
        self.data = data
        self.last_poll_successful = True

    async def async_send_command(self, command: int) -> None:
        """Authenticate, write a single command byte, then read back the result."""
        try:
            async with asyncio.timeout(_POLL_TIMEOUT), self._lock:
                client: BleakClient | None = None
                try:
                    client = await self._async_connect(self._ble_device())
                    await self._async_authenticate(client)
                    await client.write_gatt_char(
                        CH_COMMAND, bytes([command]), response=True
                    )
                    self._async_store(await self._async_read_all(client))
                finally:
                    await self._async_disconnect(client)
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        self.async_update_listeners()

    async def async_set_parameter(self, field: str, value: int) -> None:
        """Change one field of productParamA.

        The whole block is written back: read, change one field, write. That is
        what the vendor app does when it transfers settings to the device.
        """
        try:
            async with asyncio.timeout(_POLL_TIMEOUT), self._lock:
                client: BleakClient | None = None
                try:
                    client = await self._async_connect(self._ble_device())
                    await self._async_authenticate(client)
                    current = bytes(await client.read_gatt_char(CH_PARAM_A))
                    await client.write_gatt_char(
                        CH_PARAM_A,
                        protocol.write_param_a(current, field, value),
                        response=True,
                    )
                    self._async_store(await self._async_read_all(client))
                finally:
                    await self._async_disconnect(client)
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="write_failed"
            ) from err
        self.async_update_listeners()

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Take the battery level out of the advertisement, free of charge."""
        if (raw := service_info.manufacturer_data.get(MANUFACTURER_ID)) and self.data:
            self.data.values.update(protocol.parse_advertisement(bytes(raw)))
        super()._async_handle_bluetooth_event(service_info, change)
