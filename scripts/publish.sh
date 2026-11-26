#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_dir"
repo="intqwq/autodl-mcp-cli"
python_bin="${AUTODL_PYTHON:-python3}"

command -v git >/dev/null || { echo "Install Git first." >&2; exit 1; }
command -v gh >/dev/null || { echo "Install the official GitHub CLI first: https://cli.github.com/" >&2; exit 1; }
if ! gh auth status >/dev/null 2>&1; then
    echo "Sign in first: gh auth login --web --git-protocol https --scopes workflow" >&2
    exit 1
fi
if [[ "$(gh api user --jq .login)" != "intqwq" ]]; then
    echo "This release targets intqwq/autodl-mcp-cli. Sign in as intqwq before publishing." >&2
    exit 1
fi
"$python_bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Python 3.11+ is required.")'

# A release archive is a source snapshot without .git; make its own repository.
if [[ ! -e .git ]]; then
    git init --initial-branch=main
    git config user.name intqwq
    git config user.email 220658339+intqwq@users.noreply.github.com
    git add --all
    git commit -m "Release autodl CLI and MCP"
fi
if [[ -n "$(git status --porcelain)" ]]; then
    echo "Commit or stash source changes before publishing." >&2
    exit 1
fi
version="$("$python_bin" -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
tag="v$version"
commit="$(git rev-parse HEAD)"
if gh release view "$tag" --repo "$repo" >/dev/null 2>&1; then
    echo "Release $tag already exists; refusing to overwrite it." >&2
    exit 1
fi
if git remote get-url origin >/dev/null 2>&1; then
    remote="$(git remote get-url origin)"
    case "$remote" in
        https://github.com/intqwq/autodl-mcp-cli|https://github.com/intqwq/autodl-mcp-cli.git|git@github.com:intqwq/autodl-mcp-cli.git) ;;
        *) echo "Origin points elsewhere; left untouched: $remote" >&2; exit 1 ;;
    esac
fi

"$python_bin" -m venv .venv-release
.venv-release/bin/python -m pip install -e '.[dev]'
.venv-release/bin/python -m unittest discover -s tests -v
.venv-release/bin/python -m build
.venv-release/bin/python -m twine check "dist/autodl_classic_agent-$version-py3-none-any.whl" "dist/autodl_classic_agent-$version.tar.gz"
.venv-release/bin/python scripts/make_release.py

if ! git remote get-url origin >/dev/null 2>&1; then
    if gh repo view "$repo" >/dev/null 2>&1; then
        git remote add origin "https://github.com/$repo.git"
    else
        gh repo create "$repo" --public --source . --remote origin \
            --description "AutoDL GPU rentals from your terminal, Codex, and Claude Code"
    fi
fi
git -c credential.helper='!gh auth git-credential' push --set-upstream origin HEAD:main
gh release create "$tag" --repo "$repo" --target "$commit" \
    --title "autodl $version" --notes-file docs/RELEASE_NOTES.md --latest \
    "dist/autodl_classic_agent-$version-py3-none-any.whl" \
    "dist/autodl_classic_agent-$version.tar.gz" \
    "dist/autodl-$version.tar.gz" dist/SHA256SUMS
gh release view "$tag" --repo "$repo"
