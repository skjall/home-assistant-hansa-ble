"""Constants of the Home Assistant integration.

Everything about the device itself - service UUIDs, characteristics, command
bytes - lives in the hansa_ble_protocol package and is re-exported here, so
the platforms have one place to import from.
"""

from typing import Final

from hansa_ble_protocol import (
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
    CMD_CLEANING,
    CMD_COUNTER_RESET,
    CMD_NORMAL,
    CMD_OPEN,
    CMD_WINK,
    MANUFACTURER,
    MANUFACTURER_ID,
)

__all__ = [
    "AVAILABILITY_INTERVAL",
    "CH_COMMAND",
    "CH_COUNTER_A",
    "CH_COUNTER_B",
    "CH_COUNTER_C",
    "CH_NONCE",
    "CH_PARAM_A",
    "CH_PASSWORD",
    "CH_PRODUCT_INFO",
    "CH_PRODUCT_LOCATION",
    "CH_PRODUCT_NAME",
    "CH_STATE_A",
    "CH_STATE_B",
    "CMD_CLEANING",
    "CMD_COUNTER_RESET",
    "CMD_NORMAL",
    "CMD_OPEN",
    "CMD_WINK",
    "CONF_INTERVAL",
    "CONF_PIN",
    "DEFAULT_INTERVAL",
    "DOMAIN",
    "MANUFACTURER",
    "MANUFACTURER_ID",
    "MAX_INTERVAL",
    "MIN_INTERVAL",
]

DOMAIN: Final = "hansa_ble"

CONF_PIN: Final = "pin"
CONF_INTERVAL: Final = "interval"

# The faucet advertises only every few minutes and is connectable only while
# it does. Polling more often gains nothing, costs battery, and locks the
DEFAULT_INTERVAL: Final = 900
MIN_INTERVAL: Final = 120
MAX_INTERVAL: Final = 86400

# The device stays silent between advertisements, so without this hint Home
AVAILABILITY_INTERVAL: Final = 600.0
