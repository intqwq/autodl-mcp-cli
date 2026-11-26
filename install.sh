#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${AUTODL_AGENT_INSTALL_ROOT:-}" ]]; then
    install_root="$AUTODL_AGENT_INSTALL_ROOT"
elif [[ -n "${AUTODL_CLASSIC_INSTALL_ROOT:-}" ]]; then
    install_root="$AUTODL_CLASSIC_INSTALL_ROOT"
elif [[ -d "$HOME/.local/share/autodl-classic-agent/venv" ]]; then
    install_root="$HOME/.local/share/autodl-classic-agent"
else
    install_root="$HOME/.local/share/autodl"
fi
bin_dir="${AUTODL_AGENT_BIN_DIR:-${AUTODL_CLASSIC_BIN_DIR:-$HOME/.local/bin}}"
old_art_root="${AUTODL_INSTALL_ROOT:-$HOME/.local/share/autodl-agent}"
python_bin="${AUTODL_PYTHON:-python3}"
with_browser=false
case "${1:-}" in
  --with-browser) with_browser=true ;;
  "") ;;
  *) echo "Usage: bash install.sh [--with-browser]" >&2; exit 2 ;;
esac
if [[ $# -gt 1 ]]; then echo "Usage: bash install.sh [--with-browser]" >&2; exit 2; fi
"$python_bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Python 3.11+ is required.")'
mkdir -p -- "$install_root" "$bin_dir"
for command in autodl autodl-mcp autodl-classic autodl-classic-mcp autodl-desktop-login; do
    path="$bin_dir/$command"
    target="$install_root/venv/bin/$command"
    if [[ -e "$path" || -L "$path" ]]; then
        previous=""
        if [[ -L "$path" ]]; then previous="$(readlink -- "$path")"; fi
        legacy="$old_art_root/venv/bin/$command"
        case "$command" in
            autodl) stable="$install_root/venv/bin/autodl-agent" ;;
            autodl-desktop-login) stable="$target"; legacy="$target" ;;
            *) stable="$install_root/venv/bin/autodl-agent-mcp" ;;
        esac
        if [[ ! -L "$path" || ( "$previous" != "$target" && "$previous" != "$stable" && "$previous" != "$legacy" ) ]]; then
            echo "Refusing to replace unrelated $path; set AUTODL_AGENT_BIN_DIR." >&2
            exit 1
        fi
    fi
done
"$python_bin" -m venv "$install_root/venv"
extra=""
if "$with_browser"; then extra="[login]"; fi
"$install_root/venv/bin/python" -m pip install --upgrade "$project_dir$extra"
for command in autodl-classic autodl-classic-mcp autodl-desktop-login; do
    ln -sfn -- "$install_root/venv/bin/$command" "$bin_dir/$command"
done
ln -sfn -- "$install_root/venv/bin/autodl-agent" "$bin_dir/autodl"
ln -sfn -- "$install_root/venv/bin/autodl-agent-mcp" "$bin_dir/autodl-mcp"
"$bin_dir/autodl" --version
if "$with_browser"; then
    if ! command -v chromium >/dev/null && ! command -v chromium-browser >/dev/null && ! command -v google-chrome >/dev/null && ! command -v google-chrome-stable >/dev/null; then
        "$install_root/venv/bin/python" -m playwright install chromium
    fi
fi
echo "Installed. iPad/Safari login (no server browser): $bin_dir/autodl auth login"
