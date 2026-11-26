# autodl 0.7.0

AutoDL GPU rental CLI and local MCP server for Ubuntu, Codex, and Claude Code.

- Restore a stopped instance's system disk from its configured image with
  `instance reset UUID --yes` or the corresponding write-enabled MCP tool.
- No-GPU boot, same-region PAYG cloning with optional data disk copying, and clone previews.
- Live usage, instance renaming, shutdown timers, and data disk expansion quotes and orders.
- iPad Safari login without DevTools, copied HTTP headers, or a server browser.
- Read-only MCP by default; opt in to write tools with `--allow-writes`.
- Saved sessions and existing installer deployments remain compatible.
- Standard Python wheel and sdist, installer archive, and SHA-256 checksums.

## Install on Ubuntu

Python 3.11+ and `python3-venv` are required.

```bash
curl -fL https://github.com/intqwq/autodl-mcp-cli/releases/download/v0.7.0/autodl-0.7.0.tar.gz -o autodl-0.7.0.tar.gz
tar -xzf autodl-0.7.0.tar.gz
cd autodl-0.7.0
bash install.sh
export PATH="$HOME/.local/bin:$PATH"
autodl --version
```

The wheel's distribution name remains `autodl-classic-agent`; its public
commands are `autodl` and `autodl-mcp`.

This is an unofficial web-console integration; private endpoints can change.
Rentals, clones, starts, and disk expansion can incur charges. Release deletes
instance data. Shutdown timers run on AutoDL, and there is no spending cap. See README.md for full agent setup,
authentication, migration, and operating instructions.
