# Release process

Version numbers in `pyproject.toml` and `src/autodl_classic_agent/__init__.py`
must agree. Update the README download examples, changelog, and release notes
when preparing a new version.

## Publish from a terminal

Install Git and the official GitHub CLI. Authenticate to your own account:

```bash
gh auth login --web --git-protocol https --scopes workflow
```

This device/browser flow works when accessing an Ubuntu server from an iPad.
Complete the GitHub authorization yourself; never paste a GitHub token into chat.

From a clean checkout or extracted source archive:

```bash
bash scripts/publish.sh
```

The script runs the test suite, builds and checks the wheel/sdist, creates the
installer archive and checksums, then publishes the public repository
`intqwq/autodl-mcp-cli` and a versioned GitHub Release. It requires that you are signed
in as `intqwq`. It will not overwrite an existing release or replace a remote.

The repository defaults to public because it is intended for distribution.
Only source and release assets are uploaded; config/session files are ignored.

## Publish through GitHub Actions

After the repository exists, either push a matching version tag or manually
run **Release** in the Actions tab with a tag such as `v0.7.0`. The workflow
checks the version, tests, builds, and publishes the assets using the
repository's own scoped `GITHUB_TOKEN`. No external package-index token is
required. Tags must match the package version; existing releases are not replaced.

The separate CI workflow tests Python 3.11–3.14 on Ubuntu. Live account
operations are never part of CI.

## Build without publishing

```bash
python3 -m venv .venv-release
.venv-release/bin/python -m pip install -e '.[dev]'
.venv-release/bin/python -m unittest discover -s tests -v
.venv-release/bin/python -m build
.venv-release/bin/python -m twine check dist/*.whl dist/*.tar.gz
.venv-release/bin/python scripts/make_release.py
```

`make_release.py` packages tracked files from the committed source and refuses
uncommitted changes. It adds `autodl-VERSION.tar.gz` and `SHA256SUMS` to `dist/`.

## Optional future PyPI publication

The same wheel and sdist can be published under `autodl-classic-agent` after
the maintainer configures a PyPI account and the project's publishing access.
There is no automatic PyPI upload in this release. GitHub Releases already
provides public, versioned installation without a PyPI credential.
