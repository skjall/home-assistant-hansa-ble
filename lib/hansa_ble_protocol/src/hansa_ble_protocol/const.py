"""Constants of the Hansa/Oras wire protocol.

Every value here was derived from the vendor app and verified against a real
device; docs/protocol.md records how each one was established.
"""

from typing import Final

MANUFACTURER: Final = "Hansa"
MANUFACTURER_ID: Final = 305  # 0x0131

SERVICE_INFO: Final = "2be32db1-5f6b-4cbd-8803-38d6dfb16490"
SERVICE_SETTINGS: Final = "2be32db1-5f6b-5bd8-8033-8d6dfb164900"
SERVICE_TESTING: Final = "2be32db1-5f6b-6bd8-8033-8d6dfb164900"

# Handles differ per device, so everything is addressed by UUID.
CH_PRODUCT_INFO: Final = "2be32db1-5f6b-4cbd-8813-8d6dfb164900"
CH_PRODUCT_NAME: Final = "2be32db1-5f6b-4cbd-8823-8d6dfb164900"
CH_PRODUCT_LOCATION: Final = "2be32db1-5f6b-4cbd-8833-8d6dfb164900"
CH_STATE_A: Final = "2be32db1-5f6b-4cbd-8843-8d6dfb164900"
CH_STATE_B: Final = "2be32db1-5f6b-4cbd-8853-8d6dfb164900"
CH_COUNTER_A: Final = "2be32db1-5f6b-4cbd-8863-8d6dfb164900"
CH_COUNTER_B: Final = "2be32db1-5f6b-4cbd-8873-8d6dfb164900"
CH_COUNTER_C: Final = "2be32db1-5f6b-4cbd-8883-8d6dfb164900"

CH_PARAM_A: Final = "2be32db1-5f6b-5bd8-8138-d6dfb1649000"
CH_PARAM_B: Final = "2be32db1-5f6b-5bd8-8238-d6dfb1649000"
CH_PARAM_C: Final = "2be32db1-5f6b-5bd8-8338-d6dfb1649000"
CH_COMMAND: Final = "2be32db1-5f6b-5bd8-8a38-d6dfb1649000"
CH_PASSWORD: Final = "2be32db1-5f6b-5bd8-8b38-d6dfb1649000"
CH_NONCE: Final = "2be32db1-5f6b-5bd8-8e8d-6dfb16490000"

# A single byte written to CH_COMMAND once authenticated.
CMD_WINK: Final = 0x51
CMD_OPEN: Final = 0x62
CMD_CLEANING: Final = 0x73
CMD_NORMAL: Final = 0x84
CMD_LOG_RESET: Final = 0x52
CMD_COUNTER_RESET: Final = 0xA6
CMD_PAIRING_START: Final = 0x40
CMD_PAIRING_CLEAR: Final = 0x42
