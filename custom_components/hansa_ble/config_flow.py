"""Setup: the faucet is found over Bluetooth, then the PIN is asked for."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import hansa_ble_protocol as protocol
import voluptuous as vol
from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import HansaConfigEntry
from .const import (
    CH_NONCE,
    CH_PASSWORD,
    CONF_INTERVAL,
    CONF_PIN,
    DEFAULT_INTERVAL,
    DOMAIN,
    MANUFACTURER_ID,
    MAX_INTERVAL,
    MIN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# Shown as dots rather than in the clear, in the setup form and in the options.
PIN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=MIN_INTERVAL, max=MAX_INTERVAL, step=60, mode=NumberSelectorMode.BOX
    )
)


def suggested_title(info: BluetoothServiceInfoBleak) -> str:
    """Name the entry after the installation location the faucet broadcasts."""
    raw = info.manufacturer_data.get(MANUFACTURER_ID)
    if raw and (location := protocol.parse_advertisement(bytes(raw)).get("location")):
        return str(location)
    return f"Hansa {info.address[-5:].replace(':', '')}"


class HansaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the faucet."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._discovered: BluetoothServiceInfoBleak | None = None
        self._address: str | None = None
        self._title: str | None = None

    async def _async_check_pin(self, address: str, pin: str) -> str | None:
        """Log in for real. Returns an error key, or None on success."""
        device = async_ble_device_from_address(self.hass, address, connectable=True)
        if device is None:
            return "not_in_range"
        try:
            client = await establish_connection(
                BleakClient, device, address, max_attempts=4, timeout=20.0
            )
        except Exception:
            # The faucet only accepts connections during its brief advertising
            # window, so a miss here is ordinary and worth retrying.
            return "cannot_connect"
        try:
            nonce = bytes(await client.read_gatt_char(CH_NONCE))
            password = bytes(await client.read_gatt_char(CH_PASSWORD))
            await client.write_gatt_char(
                CH_PASSWORD, protocol.auth_response(nonce, password, pin), response=True
            )
            if not protocol.is_authenticated(
                bytes(await client.read_gatt_char(CH_NONCE))
            ):
                return "invalid_pin"
        except Exception:
            _LOGGER.exception("Unexpected error while checking the PIN")
            return "unknown"
        else:
            return None
        finally:
            await client.disconnect()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a faucet discovered over Bluetooth."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovered = discovery_info
        self._address = discovery_info.address
        self._title = suggested_title(discovery_info)
        self.context["title_placeholders"] = {"name": self._title}
        return await self.async_step_pin()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick from the faucets in range."""
        configured = self._async_current_ids()
        candidates = {
            info.address: suggested_title(info)
            for info in async_discovered_service_info(self.hass, connectable=True)
            if MANUFACTURER_ID in info.manufacturer_data
            and info.address not in configured
        }
        if not candidates:
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            self._address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(self._address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._title = candidates[self._address]
            return await self.async_step_pin()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(candidates)}),
        )

    async def async_step_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the PIN and verify it against the device."""
        assert self._address is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            pin = user_input[CONF_PIN]
            if error := await self._async_check_pin(self._address, pin):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=self._title or self._address,
                    data={CONF_ADDRESS: self._address, CONF_PIN: pin},
                )

        return self.async_show_form(
            step_id="pin",
            data_schema=vol.Schema({vol.Required(CONF_PIN): PIN_SELECTOR}),
            errors=errors,
            description_placeholders={"name": self._title or self._address},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a PIN that the device no longer accepts."""
        self._address = entry_data[CONF_ADDRESS]
        self._title = self._get_reauth_entry().title
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the PIN again."""
        assert self._address is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            pin = user_input[CONF_PIN]
            if error := await self._async_check_pin(self._address, pin):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_PIN: pin}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PIN): PIN_SELECTOR}),
            errors=errors,
            description_placeholders={"name": self._title or self._address},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point an existing entry at another faucet, or fix its PIN."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        configured = self._async_current_ids()
        candidates = {
            info.address: suggested_title(info)
            for info in async_discovered_service_info(self.hass, connectable=True)
            if MANUFACTURER_ID in info.manufacturer_data
            and (
                info.address not in configured
                or info.address == entry.data[CONF_ADDRESS]
            )
        }
        candidates.setdefault(entry.data[CONF_ADDRESS], entry.title)

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_mismatch(reason="another_device")
            if error := await self._async_check_pin(address, user_input[CONF_PIN]):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_ADDRESS: address,
                        CONF_PIN: user_input[CONF_PIN],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS, default=entry.data[CONF_ADDRESS]
                    ): vol.In(candidates),
                    vol.Required(CONF_PIN): PIN_SELECTOR,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: HansaConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HansaOptionsFlow()


class HansaOptionsFlow(OptionsFlow):
    """Change the PIN and how often the faucet is polled."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            user_input[CONF_INTERVAL] = int(user_input[CONF_INTERVAL])
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PIN,
                        default=options.get(
                            CONF_PIN, self.config_entry.data.get(CONF_PIN, "")
                        ),
                    ): PIN_SELECTOR,
                    vol.Required(
                        CONF_INTERVAL,
                        default=options.get(CONF_INTERVAL, DEFAULT_INTERVAL),
                    ): INTERVAL_SELECTOR,
                }
            ),
        )
