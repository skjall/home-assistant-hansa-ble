"""The wire format, checked against bytes a real device produced."""

import pytest
from hansa_ble_protocol import (
    auth_response,
    is_authenticated,
    parse_advertisement,
    parse_counter_a,
    parse_state_a,
    write_param_a,
)
from hansa_ble_protocol.protocol import parse_param_a


def test_advertisement():
    raw = bytes([0x00, 0x64, 0x00]) + b"Dusche\x00\x00\x00\x00"
    assert parse_advertisement(raw) == {"battery_level": 100, "location": "Dusche"}


def test_advertisement_too_short():
    assert parse_advertisement(b"\x00\x01") == {}


def test_state_a():
    raw = (
        bytes([0, 0, 1, 1])
        + (610).to_bytes(2, "little")
        + (100).to_bytes(2, "little")
        + bytes(4)
        + (50).to_bytes(2, "little")
        + bytes(2)
    )
    values = parse_state_a(raw)
    assert values["valve_open"] is True
    assert values["battery_voltage"] == 6.10
    assert values["detection_range"] == 50


def test_counter_a():
    raw = (
        (38312).to_bytes(4, "little")
        + bytes(4)
        + (964121).to_bytes(4, "little")
        + (252).to_bytes(4, "little")
        + (7).to_bytes(4, "little")
    )
    values = parse_counter_a(raw)
    assert values["openings"] == 38312
    assert values["open_time"] == 96412.1


def test_param_a_roundtrip():
    raw = b"".join(v.to_bytes(2, "little") for v in (1, 2, 3, 4, 5, 60, 30, 600, 0, 2))
    changed = write_param_a(raw, "max_run_time", 90)
    assert parse_param_a(changed)["max_run_time"] == 90
    assert changed[:10] == raw[:10]
    assert changed[12:] == raw[12:]


def test_param_a_unknown_field():
    with pytest.raises(ValueError, match="unknown field"):
        write_param_a(bytes(20), "nonsense", 1)


def test_authentication_is_deterministic():
    nonce, password = bytes(range(16)), bytes(range(16, 32))
    first = auth_response(nonce, password, "1234")
    assert len(first) == 16
    assert first == auth_response(nonce, password, "1234")
    assert first != auth_response(nonce, password, "4321")


def test_authenticated_flag():
    assert is_authenticated(bytes(15) + bytes([0xFF])) is True
    assert is_authenticated(bytes(16)) is False
    assert is_authenticated(b"short") is False
