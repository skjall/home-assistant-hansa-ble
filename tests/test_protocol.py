"""The wire format, checked against bytes the real device produced."""

from __future__ import annotations

import pytest

from custom_components.hansa_ble import protocol


def test_advertisement() -> None:
    """Battery level and location come out of the advertisement."""
    raw = bytes([0x00, 0x64, 0x00]) + b"Dusche\x00\x00\x00\x00"
    assert protocol.parse_advertisement(raw) == {
        "battery_level": 100,
        "location": "Dusche",
    }


def test_advertisement_too_short() -> None:
    """A truncated advertisement yields nothing rather than an exception."""
    assert protocol.parse_advertisement(b"\x00\x01") == {}


def test_state_a() -> None:
    """Voltage is hundredths of a volt, the valve flag is a plain byte."""
    raw = (
        bytes([0, 0, 1, 1])
        + (610).to_bytes(2, "little")
        + (100).to_bytes(2, "little")
        + bytes(4)
        + (50).to_bytes(2, "little")
        + bytes(2)
    )
    values = protocol.parse_state_a(raw)
    assert values["valve_open"] is True
    assert values["battery_voltage"] == 6.10
    assert values["battery_level"] == 100
    assert values["detection_range"] == 50


def test_counters() -> None:
    """Open time arrives in tenths of a second."""
    raw = (
        (38312).to_bytes(4, "little")
        + bytes(4)
        + (964121).to_bytes(4, "little")
        + (252).to_bytes(4, "little")
        + (7).to_bytes(4, "little")
    )
    values = protocol.parse_counter_a(raw)
    assert values["openings"] == 38312
    assert values["open_time"] == 96412.1
    assert values["auto_flushes"] == 252


def test_param_a_roundtrip() -> None:
    """Writing one field leaves every other byte untouched."""
    raw = b"".join(v.to_bytes(2, "little") for v in (1, 2, 3, 4, 5, 60, 30, 600, 0, 2))
    assert protocol.parse_param_a(raw)["max_run_time"] == 60

    changed = protocol.write_param_a(raw, "max_run_time", 90)
    assert len(changed) == len(raw)
    assert protocol.parse_param_a(changed)["max_run_time"] == 90
    assert changed[:10] == raw[:10]
    assert changed[12:] == raw[12:]


def test_param_a_unknown_field() -> None:
    """An unknown field is a programming error, not a silent no-op."""
    with pytest.raises(ValueError, match="unknown field"):
        protocol.write_param_a(bytes(20), "nonsense", 1)


def test_authentication_is_deterministic() -> None:
    """The same nonce and PIN always produce the same 16 bytes."""
    nonce = bytes(range(16))
    password = bytes(range(16, 32))
    first = protocol.auth_response(nonce, password, "1234")
    assert len(first) == 16
    assert first == protocol.auth_response(nonce, password, "1234")
    assert first != protocol.auth_response(nonce, password, "4321")


def test_authenticated_flag() -> None:
    """Byte 15 of the nonce is what the faucet flips on success."""
    assert protocol.is_authenticated(bytes(15) + bytes([0xFF])) is True
    assert protocol.is_authenticated(bytes(16)) is False
    assert protocol.is_authenticated(b"short") is False
