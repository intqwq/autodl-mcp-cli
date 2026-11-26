#!/usr/bin/env bash
# Remove only the original Art install created by this conversation's installer.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$script_dir/uninstall_old.py"
