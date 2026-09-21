# Hansa Faucet (BLE)

Home Assistant integration for Hansa / Oras electronic faucets that speak
Bluetooth Low Energy — the ones the vendor's HANSA app talks to.

It reads what the faucet knows about itself and writes back what the app can
write: open the valve, put it into cleaning mode and out again, adjust the
timings. Everything happens locally over BLE; no cloud, no vendor account.

## Supported devices

Hansa and Oras electronic faucets whose sensor module speaks Bluetooth Low
Energy — the ones the HANSA app finds. Verified against:

| Model | Sensor | Hardware | Software |
| --- | --- | --- | --- |
| Basin faucet (`57162279`) | `1001424` | 1.30 | 45 |

Other faucets of the same family advertise under manufacturer ID `0x0131`
and expose the same services; they are expected to work, but only the row
above has actually been tried. If yours works, a note in the issue tracker
is welcome.

The faucet's *installation location*, set in the app, is what this integration
names the device after.

## What you get

| Entity | Kind | Notes |
| --- | --- | --- |
| Valve | binary sensor | open while water is flowing |
| Total volume | sensor | litres, as counted by the faucet |
| Openings, Open time, Automatic flushes | sensors | lifetime counters |
| Since last use, Until next flush | sensors | drives the automatic hygiene flush |
| Battery, Battery voltage | sensors | the level also arrives in the advertisement |
| Sensor error code | sensor | diagnostic |
| Open valve, Cleaning mode, Normal mode | buttons | need the PIN |
| Identify | button | one short flash and a splash of water, to find the device |
| Reset interim counter | button | needs the PIN |
| Maximum run time, Manual flush time, Cleaning mode duration, Run-on time | numbers | written back to the device |

The total volume is *computed by the faucet* from open time multiplied by a
configured flow rate, not measured. Treat it as an estimate.

## Use cases

- **Leak and runtime watch.** *Valve* turns on the moment water flows. An
  automation that sees it open for longer than it ever should can warn you, or
  close the main valve.
- **Water usage in the energy dashboard.** *Total volume* is a
  `total_increasing` water sensor, so it can be added as a water source — with
  the caveat under [Notes and limitations](#notes-and-limitations).
- **Hygiene flushing you can see.** *Until next flush* and *Automatic flushes*
  make the faucet's own flushing visible, so a holiday absence can be planned
  around it.
- **Cleaning without fumbling.** *Cleaning mode* holds the valve shut while the
  basin is scrubbed; *Normal mode* ends it. No need to find the app first.
- **Presence, quietly.** *Since last use* is a reliable, camera-free signal
  that somebody is up and about.

## Examples

Warn when water has been running for five minutes:

```yaml
automation:
  - alias: "Faucet running too long"
    triggers:
      - trigger: state
        entity_id: binary_sensor.dusche_valve
        to: "on"
        for: "00:05:00"
    actions:
      - action: notify.persistent_notification
        data:
          message: "The faucet has been running for five minutes."
```

Put the faucet into cleaning mode and back again:

```yaml
script:
  clean_the_basin:
    sequence:
      - action: button.press
        target:
          entity_id: button.dusche_cleaning_mode
      - delay: "00:10:00"
      - action: button.press
        target:
          entity_id: button.dusche_normal_mode
```

## How data is fetched

The faucet sleeps. Every few minutes it sends one advertisement, and only
during that brief window will it accept a connection — a timer-based poll
would mostly knock on a closed door.

So the integration listens for advertisements instead. Each one is asked
whether a poll is due; if it is, Home Assistant connects right then, reads
every characteristic in one session and disconnects. The interval you
configure is therefore a *minimum* gap, not a schedule: the real gap is
however long it takes the faucet to wake up next.

Two consequences worth knowing:

- The battery level arrives with each advertisement, so it stays fresh even
  between polls.
- After disconnecting, the integration clears the cached advertisement, because
  Home Assistant otherwise discards the next wake-up packet as a duplicate —
  the faucet's advertisement rarely changes.

Commands do not wait for the next poll. A button press connects, authenticates,
writes, and reads the new state back over the same connection.

## Requirements

- Home Assistant 2026.5 or newer (that release added
  `async_clear_advertisement_history`, without which a sleeping faucet is only
  ever polled once)
- A Bluetooth adapter or an ESPHome Bluetooth proxy within range of the faucet.
  Range matters more than it sounds: the faucet sits under a basin, often
  behind metal. A proxy with an external antenna is worth the trouble.
- The PIN you set in the HANSA app. Readings work without it; commands and
  settings do not.

## Installation

### HACS (recommended)

1. HACS → three-dot menu → *Custom repositories*
2. Add this repository's URL, category *Integration*
3. Install *Hansa Faucet (BLE)*, then restart Home Assistant

### Manually

Copy `custom_components/hansa_ble` into your Home Assistant `config` directory
so that it ends up at `config/custom_components/hansa_ble`, then restart.

## Setup

The faucet is discovered on its own once it advertises — *Settings → Devices &
Services* will offer it. Otherwise add it through *Add integration → Hansa
Faucet (BLE)*.

You will be asked for the PIN, and it is verified against the faucet before
the entry is created. If that fails with *could not connect*, simply try again:
the faucet accepts connections only during the brief moment it advertises, so
roughly one attempt in three lands.

The entry is named after the installation location the faucet broadcasts (the
one you set in the app), and that name becomes the device name.

## Configuration

Under the integration's *Configure*:

- **PIN** — needed for commands and settings.
- **Polling interval** (default 900 s) — how long to wait before connecting
  again. The faucet is only reachable while it advertises, so the real gap can
  be longer. Shorter intervals cost battery and lock the vendor app out while
  a connection is open.

## Removal

*Settings → Devices & Services → Hansa Faucet (BLE) → Delete*. If installed
through HACS, uninstall it there as well and restart.

## Notes and limitations

- **One connection at a time.** While Home Assistant is connected the vendor
  app cannot connect, and vice versa.
- **The factory reset is not exposed.** The command byte is known and
  deliberately left out, so nobody triggers it by accident.
- Some fields of `productParamB` and `productParamC` are located but not yet
  exposed; see [docs/protocol.md](docs/protocol.md).

## Troubleshooting

**"Could not connect" while entering the PIN.** Ordinary — the faucet only
accepts connections for the moment it advertises. Try again; roughly one
attempt in three lands. Running a tap briefly wakes it.

**Entities stay unavailable.** No advertisement has reached Home Assistant yet.
Check that a Bluetooth adapter or proxy is in range: *Settings → Devices &
Services → Bluetooth* lists what each adapter hears. The faucet appears as
`ORAS`.

**The faucet is heard but never polled.** Something else is connected to it.
The vendor app blocks Home Assistant for as long as it is open on that faucet;
close it.

**Everything worked, now the PIN is refused.** The PIN was changed in the app.
Home Assistant will ask you to re-enter it.

**Weak signal.** The faucet sits under a basin, often behind metal. An ESPHome
proxy right next to it, with an external antenna, is the difference between
−86 dBm and −40 dBm. A board with a PCB antenna is usually not enough.

For a bug report, attach the diagnostics from the integration's three-dot menu.
They contain the raw settings block and the last advertisement, with the PIN,
address and serial number removed.

## How this works

The protocol was worked out from the vendor app and verified against a real
device. [docs/protocol.md](docs/protocol.md) documents the advertisement
layout, the characteristics with their byte offsets, the command bytes and the
login exchange.

This is interoperability work: it lets an independently written program talk
to hardware you own. No vendor code is copied into this repository, and the
app binary it was derived from is not redistributed here.

Not affiliated with, endorsed by, or supported by Hansa or Oras. All
trademarks belong to their owners.

## Quality scale

This integration meets all 44 rules of the Home Assistant
[Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
up to and including Platinum. The per-rule status lives in
[`custom_components/hansa_ble/quality_scale.yaml`](custom_components/hansa_ble/quality_scale.yaml),
and `scripts/check_quality_scale.py` re-proves 36 of those rules mechanically on
every commit, so a claim cannot silently rot.

The manifest declares `"quality_scale": "custom"`, because Home Assistant reports
that tier for every integration outside core regardless of what the manifest says
(`Integration.quality_scale` in `loader.py`). A core tier there would be a claim the
runtime never repeats.

## License

MIT — see [LICENSE](LICENSE).
