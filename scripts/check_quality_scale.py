#!/usr/bin/env python3
"""Hold the integration to the tier it claims.

quality_scale.yaml is a promise. This script checks the part of that promise
a machine can check, and fails the commit when the code has drifted below it.
Rules that only a human can judge are listed under NOT_CHECKABLE, so that the
gap between "checked" and "claimed" stays visible instead of implied.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "hansa_ble"
PLATFORMS = ("binary_sensor", "button", "number", "sensor")

# Rules whose verdict needs a human: documentation prose, process questions,
# the quality of a dependency. Claiming them is fine; proving them is not.
NOT_CHECKABLE = {
    "appropriate-polling",
    "async-dependency",
    "docs-actions",
    "docs-conditions",
    "docs-triggers",
    "entity-category",
    "entity-device-class",
    "entity-event-setup",
    "log-when-unavailable",
    "repair-issues",
    "stale-devices",
    "unique-config-entry",
    # Coverage has a gate of its own: scripts/check_coverage.py.
    "config-flow-test-coverage",
    "test-coverage",
}

# Each documentation rule maps to a heading the README has to carry. The
# wording of a section is nobody's business here; its absence is.
DOC_SECTIONS = {
    "docs-high-level-description": "# Hansa Faucet",
    "docs-installation-instructions": "## Installation",
    "docs-removal-instructions": "## Removal",
    "docs-configuration-parameters": "## Configuration",
    "docs-installation-parameters": "## Setup",
    "docs-supported-devices": "## Supported devices",
    "docs-supported-functions": "## What you get",
    "docs-data-update": "## How data is fetched",
    "docs-known-limitations": "## Notes and limitations",
    "docs-troubleshooting": "## Troubleshooting",
    "docs-examples": "## Examples",
    "docs-use-cases": "## Use cases",
}

failures: list[str] = []


def fail(rule: str, message: str) -> None:
    failures.append(f"{rule}: {message}")


def source(name: str) -> str:
    path = PKG / f"{name}.py"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_json(relative: str) -> dict:
    path = PKG / relative
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# --- individual rules -------------------------------------------------------


def check_common_modules() -> None:
    for name in ("coordinator", "entity"):
        if not (PKG / f"{name}.py").exists():
            fail("common-modules", f"{name}.py is missing")


def check_runtime_data() -> None:
    init = source("__init__")
    if "runtime_data" not in init:
        fail("runtime-data", "__init__.py never assigns entry.runtime_data")
    if re.search(r"hass\.data\[\s*DOMAIN", init):
        fail("runtime-data", "__init__.py still uses hass.data[DOMAIN]")
    if not re.search(r"^type \w+ConfigEntry = ConfigEntry\[", init, re.M):
        fail("runtime-data", "no typed ConfigEntry alias in __init__.py")


def check_parallel_updates() -> None:
    for platform in PLATFORMS:
        if not re.search(r"^PARALLEL_UPDATES\s*=", source(platform), re.M):
            fail("parallel-updates", f"{platform}.py does not set PARALLEL_UPDATES")


def check_entity_basics() -> None:
    entity = source("entity")
    if "_attr_has_entity_name = True" not in entity:
        fail("has-entity-name", "the base entity does not set _attr_has_entity_name")
    if "_attr_unique_id" not in entity:
        fail("entity-unique-id", "the base entity does not set _attr_unique_id")


def check_config_flow() -> None:
    flow = source("config_flow")
    manifest = load_json("manifest.json")
    if not manifest.get("config_flow"):
        fail("config-flow", 'manifest.json does not set "config_flow": true')
    if not flow:
        fail("config-flow", "config_flow.py is missing")
    if "errors" not in flow:
        fail("test-before-configure", "the flow reports no errors to the user")


def check_test_before_setup() -> None:
    if "ConfigEntryNotReady" not in source("__init__"):
        fail("test-before-setup", "__init__.py never raises ConfigEntryNotReady")


def check_unloading() -> None:
    if "async def async_unload_entry" not in source("__init__"):
        fail("config-entry-unloading", "async_unload_entry is missing")


def check_flows(rule: str, *steps: str) -> None:
    flow = source("config_flow")
    for step in steps:
        if f"async def {step}" not in flow:
            fail(rule, f"{step} is missing")


def check_entity_unavailable() -> None:
    if "def available" not in source("entity") + "".join(source(p) for p in PLATFORMS):
        fail("entity-unavailable", "no entity narrows availability")


def check_action_exceptions() -> None:
    coordinator = source("coordinator")
    if "HomeAssistantError" not in coordinator:
        fail("action-exceptions", "the coordinator raises no HomeAssistantError")


def _translation_keys() -> dict[str, set[str]]:
    keys: dict[str, set[str]] = {p: set() for p in PLATFORMS}
    for platform in PLATFORMS:
        path = PKG / f"{platform}.py"
        if not path.exists():
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.keyword)
                and node.arg == "translation_key"
                and isinstance(node.value, ast.Constant)
                and node.value.value
            ):
                keys[platform].add(node.value.value)
    # The base entity derives a key from the entity's own key.
    keys["binary_sensor"].add("valve_open")
    return keys


def check_entity_translations() -> None:
    strings = load_json("strings.json")
    for platform, keys in _translation_keys().items():
        have = set(strings.get("entity", {}).get(platform, {}))
        for missing in sorted(keys - have):
            fail(
                "entity-translations", f"strings.json lacks entity.{platform}.{missing}"
            )


def check_icon_translations() -> None:
    icons = load_json("icons.json")
    if not icons:
        fail("icon-translations", "icons.json is missing")
    keys = _translation_keys()
    for platform, entries in icons.get("entity", {}).items():
        for stray in sorted(set(entries) - keys.get(platform, set())):
            fail("icon-translations", f"icons.json: {platform}.{stray} has no entity")
    # An icon= on an EntityDescription bypasses the translations entirely.
    for platform in PLATFORMS:
        if re.search(r"\bicon\s*=\s*[\"']mdi:", source(platform)):
            fail("icon-translations", f"{platform}.py hardcodes an mdi: icon")


def check_exception_translations() -> None:
    strings = load_json("strings.json")
    known = set(strings.get("exceptions", {}))
    for name in ("coordinator", "__init__"):
        text = source(name)
        for match in re.finditer(r"translation_key=\"([^\"]+)\"", text):
            key = match.group(1)
            if key not in known:
                fail(
                    "exception-translations",
                    f"{name}.py raises '{key}', absent from strings.json exceptions",
                )


def _missing_keys(reference: dict, actual: dict, path: str = "") -> list[str]:
    """List the keys of the reference that the translation does not have."""
    missing: list[str] = []
    for key, value in reference.items():
        if key not in actual:
            missing.append(path + key)
        elif isinstance(value, dict):
            missing.extend(_missing_keys(value, actual[key], f"{path}{key}."))
    return missing


def check_translations_complete() -> None:
    strings = load_json("strings.json")
    for language in ("en", "de"):
        translation = load_json(f"translations/{language}.json")
        if not translation:
            fail("entity-translations", f"translations/{language}.json is missing")
            continue
        for entry in _missing_keys(strings, translation)[:10]:
            fail("entity-translations", f"translations/{language}.json lacks {entry}")


def check_manifest() -> None:
    manifest = load_json("manifest.json")
    for key in (
        "domain",
        "name",
        "version",
        "codeowners",
        "documentation",
        "issue_tracker",
        "integration_type",
        "iot_class",
    ):
        if not manifest.get(key):
            fail("integration-owner", f"manifest.json lacks {key}")
    if not manifest.get("codeowners"):
        fail("integration-owner", "manifest.json names no codeowner")


def check_brands() -> None:
    icon = PKG / "brand" / "icon.png"
    if not icon.exists():
        fail("brands", "brand/icon.png is missing")
        return
    # A local brand image only works from 2026.3 onwards; say so in hacs.json.
    minimum = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8")).get(
        "homeassistant", "0"
    )
    if tuple(int(p) for p in minimum.split(".")[:2]) < (2026, 3):
        fail(
            "brands",
            f"hacs.json requires {minimum}, but local brand images need 2026.3",
        )


def check_dependency_transparency() -> None:
    """The wire protocol has to come from PyPI, not from inside the integration."""
    manifest = load_json("manifest.json")
    requirements = manifest.get("requirements", [])
    if not any(r.startswith("hansa-ble-protocol==") for r in requirements):
        fail(
            "dependency-transparency",
            "manifest.json does not require a pinned hansa-ble-protocol",
        )
    if (PKG / "protocol.py").exists():
        fail(
            "dependency-transparency",
            "protocol.py is back in the integration; it belongs in the package",
        )


def check_strict_typing() -> None:
    if not (PKG / "py.typed").exists():
        fail("strict-typing", "py.typed is missing")
    # mypy itself runs as its own pre-commit hook; claiming the rule without
    # that hook in place would make the claim unverifiable.
    config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    if "run_mypy.sh" not in config:
        fail("strict-typing", "no mypy hook in .pre-commit-config.yaml")


def check_diagnostics() -> None:
    if not (PKG / "diagnostics.py").exists():
        fail("diagnostics", "diagnostics.py is missing")


def check_devices() -> None:
    if "DeviceInfo" not in source("entity"):
        fail("devices", "the base entity registers no device")


def check_docs(rule: str) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    heading = DOC_SECTIONS[rule]
    if heading not in readme:
        fail(rule, f"README.md has no section '{heading}'")


def check_disabled_by_default() -> None:
    if "entity_registry_enabled_default" not in "".join(
        source(platform) for platform in PLATFORMS
    ):
        fail(
            "entity-disabled-by-default",
            "no entity is noisy enough to be disabled by default - is that right?",
        )


def check_discovery() -> None:
    manifest = load_json("manifest.json")
    if not manifest.get("bluetooth"):
        fail("discovery", "manifest.json declares no bluetooth matcher")
    if "async_step_bluetooth" not in source("config_flow"):
        fail("discovery", "the flow has no bluetooth step")


CHECKS = {
    "common-modules": check_common_modules,
    "runtime-data": check_runtime_data,
    "parallel-updates": check_parallel_updates,
    "has-entity-name": check_entity_basics,
    "entity-unique-id": check_entity_basics,
    "config-flow": check_config_flow,
    "test-before-configure": check_config_flow,
    "test-before-setup": check_test_before_setup,
    "config-entry-unloading": check_unloading,
    "reauthentication-flow": lambda: check_flows(
        "reauthentication-flow", "async_step_reauth", "async_step_reauth_confirm"
    ),
    "reconfiguration-flow": lambda: check_flows(
        "reconfiguration-flow", "async_step_reconfigure"
    ),
    "entity-unavailable": check_entity_unavailable,
    "action-exceptions": check_action_exceptions,
    "entity-translations": lambda: (
        check_entity_translations(),
        check_translations_complete(),
    ),
    "icon-translations": check_icon_translations,
    "exception-translations": check_exception_translations,
    "integration-owner": check_manifest,
    "brands": check_brands,
    "diagnostics": check_diagnostics,
    "strict-typing": check_strict_typing,
    "dependency-transparency": check_dependency_transparency,
    "devices": check_devices,
    "discovery": check_discovery,
    "entity-disabled-by-default": check_disabled_by_default,
    **{rule: (lambda r=rule: check_docs(r)) for rule in DOC_SECTIONS},
}


def main() -> int:
    import yaml

    scale = yaml.safe_load((PKG / "quality_scale.yaml").read_text(encoding="utf-8"))
    rules = scale.get("rules", {})

    claimed: set[str] = set()
    for name, value in rules.items():
        slug = name.replace("_", "-")
        status = value if isinstance(value, str) else value.get("status")
        if status == "done":
            claimed.add(slug)
        elif status not in ("todo", "exempt"):
            fail(slug, f"unknown status '{status}'")

    for slug in sorted(claimed):
        if check := CHECKS.get(slug):
            check()
        elif slug not in NOT_CHECKABLE:
            fail(slug, "claimed as done, but no check knows this rule")

    # A rule that is checkable and passes but is not claimed is worth knowing
    # about; that is a note, not a failure.
    notes = [
        slug
        for slug in CHECKS
        if slug not in claimed and rules.get(slug.replace("-", "_")) is None
    ]

    if failures:
        print("Quality scale: the code is below what quality_scale.yaml claims\n")
        for line in failures:
            print(f"  FAIL  {line}")
        print(f"\n{len(failures)} problem(s). Fix them, or downgrade the claim.")
        return 1

    print(f"Quality scale: {len(claimed)} rules claimed, ", end="")
    print(f"{len(claimed & set(CHECKS))} machine-checked, all hold.")
    if notes:
        print("  note: not claimed yet: " + ", ".join(sorted(notes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
