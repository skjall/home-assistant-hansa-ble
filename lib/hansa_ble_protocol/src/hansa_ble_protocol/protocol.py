"""Wire format of the Hansa/Oras faucet: authentication and decoding.

Reconstructed from the vendor app and checked against a real device. All
integers are little endian, times are seconds, valve open time is in tenths
of a second and the battery voltage is in hundredths of a volt.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESCCM

# Fixed bootstrap key taken from the vendor app: sixteen 0x01 bytes.
_BOOTSTRAP_KEY = bytes([0x01] * 16)

# CCM with L=2 leaves 15-L = 13 bytes of nonce.
_NONCE_LEN = 13


def _ctr_keystream(key: bytes, nonce: bytes, blocks: int) -> bytes:
    """CCM keystream A_1..A_n. A_0 only feeds the tag and is not needed here."""
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    stream = b""
    for counter in range(1, blocks + 1):
        block = bytes([1]) + nonce + counter.to_bytes(2, "big")  # flags: L-1 = 1
        encryptor = cipher.encryptor()
        stream += encryptor.update(block) + encryptor.finalize()
    return stream


def session_key(nonce: bytes, password: bytes) -> bytes:
    """Derive the session key from the nonce and the password characteristic.

    The app nominally decrypts this with AES-CCM, but the tag area of the
    buffer is all zeroes, so an authenticated decrypt could never verify.
    Only the CTR half matters, and that is a plain XOR with the keystream.
    """
    keystream = _ctr_keystream(_BOOTSTRAP_KEY, nonce[:_NONCE_LEN], 1)
    return bytes(a ^ b for a, b in zip(password[:16], keystream, strict=False))


def auth_response(nonce: bytes, password: bytes, pin: str) -> bytes:
    """Build the 16 bytes written back to the password characteristic."""
    ccm = AESCCM(session_key(nonce, password), tag_length=8)
    digest = hashlib.md5(pin.encode(), usedforsecurity=False).digest()
    return ccm.encrypt(nonce[:_NONCE_LEN], digest, None)[:16]


def is_authenticated(nonce: bytes) -> bool:
    """Report whether the faucet flipped byte 15 of the nonce to 0xFF."""
    return len(nonce) > 15 and nonce[15] == 0xFF


def _u16(data: bytes, offset: int) -> int:
    """Two bytes, little endian."""
    return int.from_bytes(data[offset : offset + 2], "little")


def _u32(data: bytes, offset: int) -> int:
    """Four bytes, little endian."""
    return int.from_bytes(data[offset : offset + 4], "little")


def _text(data: bytes) -> str:
    """Decode an ASCII field padded with NUL bytes."""
    return data.decode("ascii", "replace").replace("\x00", " ").strip()


def parse_advertisement(manufacturer_data: bytes) -> dict[str, Any]:
    """Battery level and installation location, no connection required."""
    if len(manufacturer_data) < 13:
        return {}
    return {
        "battery_level": manufacturer_data[1] & 0x7F,
        "location": _text(manufacturer_data[3:13]),
    }


def parse_state_a(data: bytes) -> dict[str, Any]:
    """Decode the status byte, valve flag, battery and detection range."""
    return {
        "device_status": data[0],
        "sensor_error": data[1],
        "operating_mode": data[2],
        "valve_open": bool(data[3]),
        "battery_voltage": _u16(data, 4) / 100,
        "battery_level": _u16(data, 6),
        "detection_range": _u16(data, 12),
    }


def parse_state_b(data: bytes) -> dict[str, Any]:
    """Decode the timers the faucet keeps: idle time and flush countdown."""
    return {
        "since_last_use": _u32(data, 4),
        "until_next_flush": _u32(data, 8),
        "since_reset": _u32(data, 12),
    }


def parse_counter_a(data: bytes) -> dict[str, Any]:
    """Decode the lifetime counters for openings, run time and flushes."""
    return {
        "openings": _u32(data, 0),
        "open_time": _u32(data, 8) / 10,  # tenths of a second
        "auto_flushes": _u32(data, 12),
        "manual_flushes": _u32(data, 16),
    }


def parse_counter_b(data: bytes) -> dict[str, Any]:
    """Decode the total volume the faucet has computed."""
    # Bytes 0-3 hold the total volume; counter A repeats after that.
    return {"total_volume": _u32(data, 0)}


def parse_counter_c(data: bytes) -> dict[str, Any]:
    """Decode the resettable interim counter."""
    return {
        "interim_volume": _u32(data, 4),
        "since_counter_reset": _u32(data, 8),
    }


def parse_product_info(data: bytes) -> dict[str, Any]:
    """Decode the sensor number and hardware revision."""
    return {"sensor_number": _text(data[0:7]), "hardware_version": _text(data[10:15])}


def parse_product_name(data: bytes) -> dict[str, Any]:
    """Decode the serial number and product name."""
    return {"serial_number": _u32(data, 0), "product_name": _text(data[4:])}


def parse_product_location(data: bytes) -> dict[str, Any]:
    """Decode the installation location and date of manufacture."""
    return {"location": _text(data[0:15]), "manufactured": _text(data[15:19])}


# productParamA: one 16 bit little endian value per field, order per the app.
PARAM_A_FIELDS: tuple[str, ...] = (
    "min_signal_level",
    "min_signal_level_flow",
    "sensitivity",
    "max_ir_power",
    "force_level",
    "max_run_time",
    "manual_flush_time",
    "cleaning_mode_time",
    "generic_a1",
    "run_on_time",
)


def parse_param_a(data: bytes) -> dict[str, Any]:
    """Decode the adjustable settings block, field by field."""
    return {
        name: _u16(data, index * 2)
        for index, name in enumerate(PARAM_A_FIELDS)
        if index * 2 + 1 < len(data)
    }


def write_param_a(current: bytes, name: str, value: int) -> bytes:
    """Change one field of productParamA, leaving the rest exactly as read."""
    if name not in PARAM_A_FIELDS:
        raise ValueError(f"unknown field: {name}")
    offset = PARAM_A_FIELDS.index(name) * 2
    updated = bytearray(current)
    updated[offset : offset + 2] = int(value).to_bytes(2, "little")
    return bytes(updated)


@dataclass(slots=True)
class FaucetData:
    """Everything one poll produces, plus what the advertisement carried."""

    values: dict[str, Any] = field(default_factory=dict)

    def get(self, name: str, default: Any = None) -> Any:
        """Return one value, or the default when the faucet did not report it."""
        return self.values.get(name, default)
