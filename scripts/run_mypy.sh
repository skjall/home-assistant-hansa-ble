#!/bin/bash
# Type checking in the same isolated environment as the tests: source
# read-only, cache inside the container. Platinum asks for strict, so strict.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE=hansa-ble-test

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker build -q -f "$ROOT/Dockerfile.test" -t "$IMAGE" "$ROOT" >/dev/null
fi

docker run --rm \
  -e HOME=/tmp \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$ROOT:/app:ro" \
  -w /app \
  "$IMAGE" \
  sh -c 'pip install -q mypy >/dev/null 2>&1; mypy --strict --ignore-missing-imports --cache-dir=/tmp/mypy custom_components/hansa_ble'
