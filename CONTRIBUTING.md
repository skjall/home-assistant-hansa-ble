# Contributing

## Before you commit

Install the hooks once:

```bash
python3 -m venv .venv && .venv/bin/pip install pre-commit
.venv/bin/pre-commit install
```

From then on every commit runs ruff, `mypy --strict`, the full test suite and
two gates that are easy to overlook. Both come from
[ha-integration-standards](https://github.com/skjall/ha-integration-standards),
not from this repository:

- **`ha-quality-scale`** holds the code to the tier that
  `custom_components/hansa_ble/quality_scale.yaml` claims. 36 of the 44 rules
  are checked mechanically; the rest need a human. A rule marked `done` whose
  check fails stops the commit — the tier cannot be kept by claiming it, only
  by holding it.
- **`ha-coverage`** enforces the coverage floors that tier requires: 100% for
  the config flow, 95% per module and overall. They are set in
  `[tool.ha_standards.coverage]`.

Raising the `rev` of that repository in `.pre-commit-config.yaml` is how this
project takes a newer set of rules; `ha-standards sync` then rewrites the
files it manages.

## Tests

```bash
ha-tests             # everything
ha-tests -k flow     # one slice
ha-types             # types only
```

Both run in Docker, against the exact Home Assistant version the integration
targets. Local Python is usually too old: Home Assistant needs 3.14.2 from
2026.3 onwards, and testing against an older release means testing an API that
is not the one users have.

The source is mounted read-only and the container runs as your own user, so a
test run cannot leave anything behind in the working tree. Everything a run
produces lands in `.artefakte/`.

## Changing the device protocol

`lib/hansa_ble_protocol/` is the only place that knows the wire format, and [docs/protocol.md](docs/protocol.md) is the record of how each byte
offset was established. If you change one, change the other, and say what you
verified it against — a real device, or the vendor app.

Never add the factory reset command. The byte is known and deliberately absent.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/) — release-please
derives the version and the changelog from them.
