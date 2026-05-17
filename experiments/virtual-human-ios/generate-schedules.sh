#!/usr/bin/env bash
# Regenerate Resources/schedules.json from the Python schedule definitions.
# Run this whenever schedules.py, personas.py, places.py, or routes.py changes.

set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cd "$here/../virtual-human"
python3 monitor.py --no-cli --no-html \
    --ios-json "$here/Resources/schedules.json"
echo "→ $here/Resources/schedules.json"
