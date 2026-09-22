# CLAUDE.md

Guidance for Claude Code in this repository.

The development ground rules are shared across integrations and are kept up to date by ha-integration-standards:

@docs/ha-integration-standards.md

## About this integration

The device is a Hansa/Oras bathroom faucet that speaks BLE. It advertises only
every few minutes and is connectable only while it does, which is why the
polling interval is long by default and why
`async_set_fallback_availability_interval` is set during setup.

The wire format lives in `lib/hansa_ble_protocol/`, published to PyPI and
pinned with `==` in the manifest. release-please raises the pin and the
package version in one commit; `ha-quality-scale` fails if they drift apart.
[docs/protocol.md](docs/protocol.md) records how each byte offset was
established — change one, change the other, and say what you verified it
against.

**Never add the factory reset command.** The byte is known and deliberately
absent.

The PIN is the only secret the integration holds. It is redacted from
diagnostics and is needed for commands, not for readings.
