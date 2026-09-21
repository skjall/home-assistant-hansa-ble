# hansa-ble-protocol

The wire protocol of Hansa and Oras electronic faucets that speak Bluetooth
Low Energy: how to decode what they send, how to encode what they accept, and
how the PIN exchange works.

This package handles bytes only. It opens no connections and pulls in no
Bluetooth stack, so it runs and tests without hardware. The Home Assistant
integration that uses it lives in the
[parent repository](https://github.com/skjall/home-assistant-hansa-ble); how
each byte offset was established is documented in
[docs/protocol.md](https://github.com/skjall/home-assistant-hansa-ble/blob/main/docs/protocol.md).

```python
from hansa_ble_protocol import parse_state_a, auth_response

state = parse_state_a(raw_bytes)
print(state["valve_open"], state["battery_level"])

# Answer the faucet's challenge with the PIN from the vendor app.
response = auth_response(nonce, password, "1234")
```

Not affiliated with, endorsed by, or supported by Hansa or Oras.

## License

MIT
