"""Diagnostics for a configured faucet."""

from __future__ import annotations

from typing import Any

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import HansaConfigEntry

# The PIN is the only secret here, and it never leaves this file.
TO_REDACT = {"pin", CONF_ADDRESS, "serial_number"}


def _redact(data: dict[str, Any]) -> dict[str, Any]:
    return {k: ("**REDACTED**" if k in TO_REDACT else v) for k, v in data.items()}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HansaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    service_info = async_last_service_info(hass, coordinator.address, connectable=True)

    return {
        "entry": {
            "data": _redact(dict(entry.data)),
            "options": _redact(dict(entry.options)),
        },
        "coordinator": {
            "available": coordinator.available,
            "last_poll_successful": coordinator.last_poll_successful,
            "last_seen": coordinator.last_seen,
            "interval": coordinator.interval,
            # Raw productParamA, so an unmapped field can be spotted from afar.
            "param_a_raw": coordinator.param_a_raw.hex()
            if coordinator.param_a_raw
            else None,
        },
        "advertisement": {
            "rssi": service_info.rssi,
            "source": service_info.source,
            "connectable": service_info.connectable,
            "manufacturer_data": {
                str(key): value.hex()
                for key, value in service_info.manufacturer_data.items()
            },
        }
        if service_info
        else None,
        "data": _redact(coordinator.data.values) if coordinator.data else None,
    }
