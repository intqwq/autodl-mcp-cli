# autodl 0.8.0

AutoDL GPU rental CLI and local MCP server for Ubuntu, Codex, and Claude Code.

- Launch AutoDL sign-in with `autodl-desktop-login` on Windows or Ubuntu.
- Save the verified session locally, or pass `--ssh USER@HOST` to save it on
  the Ubuntu host running Codex.
- Follow `docs/DESKTOP_LOGIN.md` for setup, sign-in, and manual transfer.

## Install on Ubuntu

Python 3.11+ and `python3-venv` are required.

```bash
curl -fL https://github.com/intqwq/autodl-mcp-cli/releases/download/v0.8.0/autodl-0.8.0.tar.gz -o autodl-0.8.0.tar.gz
tar -xzf autodl-0.8.0.tar.gz
cd autodl-0.8.0
bash install.sh
export PATH="$HOME/.local/bin:$PATH"
autodl --version
```

Run `bash install.sh --with-browser` when installing on an Ubuntu desktop
for desktop sign-in. The wheel's distribution name is `autodl-classic-agent`.

This is an unofficial web-console integration; private endpoints can change.
Rentals, clones, starts, and disk expansion can incur charges. Release deletes
instance data. Shutdown timers run on AutoDL, and there is no spending cap. See README.md for full agent setup,
authentication, migration, and operating instructions.
