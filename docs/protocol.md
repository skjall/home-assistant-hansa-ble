# Hansa/Oras BLE faucet — protocol

Recorded from a basin faucet: BLE name `ORAS`, address type RANDOM, device
name taken from the advertisement (the serial number as shipped, changed here
to the installation location).

Hansa belongs to the Oras Group and both use the same BLE module (a Nordic
nRF — the Nordic DFU UUID `258EAFA5-E914-47DA-95CA-C5AB0DC85B11` is present).

Worked out from the vendor app ("HANSA App", React Native) and checked step by
step against a real device. Neither the app nor the raw data taken from it is
kept in this repository — that is someone else's property. This document is our
own description of the result.

## What works passively, without connecting

The advertisement carries 18 bytes under manufacturer ID 305 (0x0131):

    00 64 00 "Dusche          "
    │  │  │  └─ 10 bytes ASCII: device name, the serial number as shipped
    │  │  └──── undocumented, always 0x00
    │  └─────── battery percentage, mask with & 0x7F
    └────────── undocumented, always 0x00

That is all — no volume, no flow rate. The format is documented in the Theengs
decoder as model ID `ORAS` and was verified against our device. The faucet
advertises roughly every 306 seconds on average.

## Services

    info      2be32db1-5f6b-4cbd-8803-38d6dfb16490
    settings  2be32db1-5f6b-5bd8-8033-8d6dfb164900
    testing   2be32db1-5f6b-6bd8-8033-8d6dfb164900

## Characteristics — verified against the device

All values are **little endian**. Cross-checked against the vendor app on
2026-09-21; every number matched. Handles are specific to this device, so
address characteristics by UUID.

### Service info `2be32db1-5f6b-4cbd-8803-38d6dfb16490`

| Handle | Short UUID | Name | Contents |
|--------|-----------|------|--------|
| 0x0012 | …8813 | productInfo | ASCII sensor number ("1001424"), hardware version ("1.30") |
| 0x0014 | …8823 | productName | 4 B serial number (LE), then ASCII product name |
| 0x0016 | …8833 | productLocation | 15 B ASCII installation location, 4 B ASCII date of manufacture |
| 0x0018 | …8843 | productStateA | see below |
| 0x001a | …8853 | productStateB | see below |
| 0x001c | …8863 | productCountersA | see below |
| 0x001e | …8873 | productCounterB | bytes 0-3 total volume in litres, then a repeat of CountersA |
| 0x0020 | …8883 | productCounterC | bytes 4-7 interim volume, bytes 8-11 time since counter reset (s) |

    productStateA (16 B)
      0      deviceState
      1      sensorErrorFlag   (0 = no error)
      2      operationMode
      3      valveState        (0 = closed)
      4-5    batteryVolt       hundredths of a volt (0x0262 = 6.10 V)
      6-7    batteryLeft       percent
      8-11   (0)
      12-13  detection range

    productStateB (20 B)
      0-1    adClose
      2-3    adOpen
      4-7    timeFromLastUse        s
      8-11   timeToNextAutoFlow     s
      12-15  timeFromLastReset      s
      16-19  (0)

    productCountersA (20 B)
      0-3    totalOpenCounter       openings of the solenoid valve
      4-7    (0)
      8-11   totalOpenTime          tenths of a second
      12-15  totalAutoFlowCount     automatic flushes
      16-19  totalManualFlowCount

### Service settings `2be32db1-5f6b-5bd8-8033-8d6dfb164900`

| Handle | Name | Access |
|--------|------|---------|
| 0x0027 / 0x0029 / 0x002b | productParamA / B / C | rw |
| 0x0035 … 0x003f | their matching min/max values | r |
| 0x002d | productCommands | w |
| 0x002f | productPassword | rw |
| 0x0031 / 0x0033 | time | rw (0x0031 returns error 5) |
| 0x0041 | nonce | rw |

### Service testing `2be32db1-5f6b-6bd8-8033-8d6dfb164900`

| 0x0023 | logParams | r + notify — all zeroes on our device throughout |

## Important: the volume is computed, not measured

The faucet has no flow sensor. It multiplies the total open time by a
configured flow rate (6 l/min on ours):

    96412.1 s × 6 l/min / 60 = 9641.2 l   -> the app shows 9641 l

The litre count is good for trends, not as a water meter. Anyone who wants it
accurate has to set that parameter to the faucet's actual flow rate.

## Reading needs no login

Every characteristic listed above returns its value **without** authenticating.
The PIN is only needed for writing. `nonce` and `productPassword` are readable
as well.

## Commands — one byte written to productCommands (handle 0x002d)

These require authentication first.

| Value | Name | Effect |
|------|------|---------|
| 0x51 (81) | WINK | LED on the sensor plus a brief burst of water (verified) |
| 0x62 (98) | OPEN | open the valve |
| 0x73 (115) | CLOSE | close the valve / cleaning mode |
| 0x84 (132) | NORMAL | back to normal operation |
| 0x52 (82) | RESET_LOG | clear the log |
| 0xA6 (166) | COUNTER_RESET | reset the interim counter |
| 0x40 (64) | START_PAIRING | start pairing |
| 0x42 (66) | REMOVE_PAIRINGS | clear pairings |
| 0x95 (149) | FACTORY_RESET | **factory reset — never send this by accident** |

## Parameters, productParamA (handle 0x0027, 20 B, 16 bit LE each)

Cross-checked against the app:

    0-1    minSignalLevel        70
    2-3    minSignalLevelFlow   150
    4-5    sensitivityFromApp     5    "sensitivity"
    6-7    maxIrPower          4096
    8-9    forcePower             0
    10-11  maxFlowTime           30 s  "maximum run time"
    12-13  maxOpenTime          120 s  "manual flush time"
    14-15  maxCloseTime        1800 s  "cleaning mode duration"
    16-17  genericParamA1         4
    18-19  aftFlowTime            1 s  "run-on time"

productParamB (0x0029) and productParamC (0x002b) follow the same pattern. The
field names are known — among them autoFlushInterval, autoFlushDuration,
flowRate and minWaterConsumption — but their byte positions have not been
verified against the device, so they are not listed here.

## Authentication (challenge-response, not BLE pairing)

1. read `nonce` (16 bytes)
2. read `productPassword`, copy it into a 24-byte buffer padded with zeroes
3. AES-CCM **decrypt**: the key is the constant
   `01010101010101010101010101010101` (sixteen 0x01), the IV is the nonce and
   the ciphertext is the password buffer → this yields the session key
4. AES-CCM **encrypt**: the key is the session key, the IV is the same nonce
   and the plaintext is the PIN → write the first 16 bytes back to
   `productPassword`
5. read `nonce` again; byte 15 set to `0xFF` means you are authenticated

The app uses `sjcl` for this. There is also a service path that bypasses the
usual PIN check; it is not described here, because the integration does not
need it.

**Implemented and verified on 2026-09-21** (`custom_components/hansa_ble/`):

- The PIN is hashed with **MD5** — recognisable from the initial values
  0x67452301 / 0xefcdab89 / 0x98badcfe / 0x10325476.
- sjcl truncates the IV to `15 - L` bytes internally, so for short messages
  that is **nonce[:13]**. Otherwise the 16-byte nonce does not fit standard
  CCM.
- The tag area of the password buffer read from the device is all zeroes, so a
  real CCM verification could never succeed. Deriving the session key only
  needs the CTR half: `A_i = 0x01 || nonce[:13] || i`, encrypted with AES-ECB
  and XORed onto the 16 bytes.
- Cryptographically the scheme is worthless — a fixed key of all 0x01, MD5,
  and a short PIN. The only real obstacle is radio range. Treat the PIN as a
  guard against accidents, not against an attacker.

## Establishing a connection

The faucet is connectable only during its brief advertising window. Connecting
on spec runs into `status=133` / `reason 0x100` (an L2CAP timeout). What works:

1. subscribe to raw advertisements (`subscribe_bluetooth_le_raw_advertisements`
   — the older `subscribe_bluetooth_le_advertisements` returns **nothing** on
   current proxies)
2. the moment a packet from the faucet arrives, connect immediately
3. on timeout, wait for the next packet and try again

In practice about one attempt in three succeeds. The faucet advertises every
half a minute to five minutes regardless of whether anybody is using it —
operating it does not measurably raise the rate.

Only one connection at a time: while the vendor app is connected nobody else
gets in, and vice versa.
