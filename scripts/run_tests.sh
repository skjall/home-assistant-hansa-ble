#!/bin/bash
# Run the tests against the Home Assistant version this integration targets.
# From 2026.3 onwards Home Assistant needs Python 3.14.2, which most systems do
# not have; without Docker you end up testing an API that is not the one users
# are running.
#
# Isolation: the source is mounted read-only, so the container cannot create or
# change anything in the working tree. Everything a run produces lands in
# .artefakte/, a directory created here beforehand and therefore owned by the
# calling user.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE=hansa-ble-test
AUSGABE="$ROOT/.artefakte"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required - see the comment above." >&2
  exit 1
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Building $IMAGE ..."
  docker build -q -f "$ROOT/Dockerfile.test" -t "$IMAGE" "$ROOT" >/dev/null
fi

mkdir -p "$AUSGABE"

docker run --rm \
  --user "$(id -u):$(id -g)" \
  --network none \
  -e HOME=/tmp \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -e COVERAGE_FILE=/ausgabe/.coverage \
  -v "$ROOT:/app:ro" \
  -v "$AUSGABE:/ausgabe" \
  -w /app \
  "$IMAGE" \
  pytest -p no:cacheprovider \
    --cov-report="json:/ausgabe/coverage.json" \
    "$@"
