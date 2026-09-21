# Contributing

## Before you commit

Install the hooks once:

```bash
python3 -m venv .venv && .venv/bin/pip install pre-commit
.venv/bin/pre-commit install
```

From then on every commit runs ruff, `mypy --strict`, the full test suite and
two gates that are easy to overlook:

- **`scripts/check_quality_scale.py`** holds the code to the tier that
  `custom_components/hansa_ble/quality_scale.yaml` claims. 35 of the 43 rules
  are checked mechanically; the rest are listed in the script as needing a
  human. A rule marked `done` whose check fails stops the commit — the tier
  cannot be kept by claiming it, only by holding it.
- **`scripts/check_coverage.py`** enforces the coverage floors that tier
  requires: 100% for the config flow, 95% per module and overall.

## Tests

```bash
./scripts/run_tests.sh          # everything
./scripts/run_tests.sh -k flow  # one slice
./scripts/run_mypy.sh           # types only
```

Both run in Docker, against the exact Home Assistant version the integration
targets. Local Python is usually too old: Home Assistant needs 3.14.2 from
2026.3 onwards, and testing against an older release means testing an API that
is not the one users have.

The source is mounted read-only and the container runs as your own user, so a
test run cannot leave anything behind in the working tree. Everything a run
produces lands in `.artefakte/`.

## Changing the device protocol

`custom_components/hansa_ble/protocol.py` is the only place that knows the wire
format, and [docs/protocol.md](docs/protocol.md) is the record of how each byte
offset was established. If you change one, change the other, and say what you
verified it against — a real device, or the vendor app.

Never add the factory reset command. The byte is known and deliberately absent.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/) — release-please
derives the version and the changelog from them.
