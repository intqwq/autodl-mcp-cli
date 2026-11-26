# AutoDL MCP and CLI

**Rent and manage AutoDL GPUs from your terminal, Codex, or Claude Code.**

[![CI](https://github.com/intqwq/autodl-mcp-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/intqwq/autodl-mcp-cli/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/intqwq/autodl-mcp-cli)](https://github.com/intqwq/autodl-mcp-cli/releases)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
[![MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

An Ubuntu-friendly CLI and local stdio MCP server for **ordinary AutoDL GPU
rentals**. Find machines, preview orders, rent instances, start and stop them,
and save images. Sign in from Windows, Ubuntu, or an iPad.

This is an independent, unofficial project. It uses AutoDL's web-console
endpoints through a pinned community backend; those endpoints can change.
Art applications and Pro instances are separate products.

## Install on Ubuntu

Requires Python 3.11+. Ubuntu 24.04 includes a suitable Python. Install venv
support if needed:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv curl
```

Download and install the versioned release:

```bash
curl -fL https://github.com/intqwq/autodl-mcp-cli/releases/download/v0.8.0/autodl-0.8.0.tar.gz -o autodl-0.8.0.tar.gz
tar -xzf autodl-0.8.0.tar.gz
cd autodl-0.8.0
bash install.sh
export PATH="$HOME/.local/bin:$PATH"
autodl --version
```

Add that `export PATH=...` line to `~/.bashrc` if `~/.local/bin` is not already
on your PATH. The application runs as your normal user in an isolated venv;
do not run `install.sh` with sudo.

Alternatively, install from source:

```bash
git clone https://github.com/intqwq/autodl-mcp-cli.git
cd autodl-mcp-cli
git checkout v0.8.0
bash install.sh
```

For pipx users, the release also includes a standard Python wheel:

```bash
pipx install 'https://github.com/intqwq/autodl-mcp-cli/releases/download/v0.8.0/autodl_classic_agent-0.8.0-py3-none-any.whl'
```

Use one installation method. The Python distribution retains the name
`autodl-classic-agent` for compatibility; the app commands are **`autodl`**
and **`autodl-mcp`**.

## Sign in from Windows or Ubuntu

Run `autodl-desktop-login` on a computer with a desktop. Sign in on AutoDL's
own login page. The script saves your session automatically after sign-in.
Pass `--ssh USER@HOST` to verify and save it on the Ubuntu host running Codex.
See the [desktop login manual](docs/DESKTOP_LOGIN.md) for PowerShell, Ubuntu,
and manual transfer instructions.

## Sign in from an iPad

No DevTools, headers, server browser, or port forwarding is needed.

1. Follow [the iPad login guide](IPAD_LOGIN.md) to create a two-action Shortcut:
   **Run JavaScript on Web Page → Copy to Clipboard**.
2. Enable **Show in Share Sheet** and accept **Safari Web Pages**. The script
   is printed by `autodl auth ipad-script`.
3. Sign in normally at [AutoDL](https://www.autodl.com) in Safari, then run
   **AutoDL Login** from Safari's Share menu. The shortcut is in the action
   list below the row of app icons; scroll down if necessary.
4. In your server's SSH terminal:

   ```bash
   autodl auth login
   autodl --json account me
   autodl --json instance list
   ```

Paste the copied session into the hidden login prompt. Verification has a
20-second deadline and preserves an existing session if it fails. Copy ordinary
text afterward to clear the session from your clipboard. The session is a secret:
never paste it into an agent conversation, GitHub issue, or log.

Credentials are stored in `~/.autodl-cli/config.toml` with mode `0600`.
Run your agents under the same Unix user. `AUTODL_CLI_HOME` overrides that
directory. A session can expire; repeat this login flow when required.

## Connect your agents

Register the bundled MCP server once on the Ubuntu host. It reuses your saved
AutoDL login, and each client starts its own process; there is no daemon or port.

**Codex CLI:**

```bash
codex mcp add autodl -- "$HOME/.local/bin/autodl-mcp" --allow-writes
codex mcp list
```

**Claude Code, across all projects:**

```bash
claude mcp add --transport stdio --scope user autodl -- \
  "$HOME/.local/bin/autodl-mcp" --allow-writes
claude mcp list
```

Open a new session and check `/mcp`. Then ask:

> Use AutoDL to list my instances and find available RTX 5090 machines.
> Show me hourly prices before renting anything.

| Server option | Effect |
| --- | --- |
| No flags | Read-only tools, live usage, clone and disk price previews, and offline `plan_rental` |
| `--allow-writes` | Enables rental, clone, start, stop, rename, reset, timers, disk growth, release, and image saving |
| `--allow-secrets` | Allows instance SSH/Jupyter credentials in results |
| `--timeout 180` | Sets the command timeout in seconds; maximum 600 |

Renting, cloning, starting, and expanding disks can incur charges. Stop
interrupts work, and release deletes instance data. `shutdown-at` sets an
AutoDL shutdown timer. The tool has no spending cap or background watchdog.
Instance credentials are masked by default; the configured web login token is
filtered even with `--allow-secrets`. Agents with shell access under your Unix
account can still read that account's files.

See [agent operating guidance](AGENTS.md) and [configuration examples](examples).
When using pipx, replace the executable path above if your pipx binary directory
differs from `~/.local/bin`.

## Terminal workflow

```bash
# Inspect inventory and choose actual machine/image IDs from the results.
autodl --json account balance
autodl --json gpu find 5090 -a
autodl --json gpu machines --gpu "EXACT_GPU_NAME" --idle 1 --sort price
autodl --json image list -f pytorch
autodl --json image list-private

# Offline preview: no login or API request.
autodl plan --machine-id MACHINE_ID --image IMAGE_UUID --gpu-num 1

# Rent a machine (billable), then inspect its state.
autodl --json instance create --machine-id MACHINE_ID --image IMAGE_UUID
autodl --json instance list
autodl --json instance detail INSTANCE_UUID

# Lifecycle operations.
autodl --json instance power-on INSTANCE_UUID
autodl --json instance power-off INSTANCE_UUID

# Permanently release an instance and its data.
autodl --json instance release INSTANCE_UUID --yes
```

Creation accepts `--gpu-num`, `--name`, and `--data-disk GB`. Use
`--private-image IMAGE_UUID` instead of `--image` for a saved image.
For the offline planner, use `--image IMAGE_UUID --private-image`.

The pinned backend's JSON money fields use **thousandths of a yuan**. Verify
whether a price is per GPU or per instance and account for extra storage.
Inventory can change between listing and ordering. If a mutation times out,
list instances before trying again. Poll `instance list` by exact UUID for
state changes; `instance detail` is a configuration snapshot.

Use SSH separately to run jobs and transfer files. This tool creates PAYG
rentals; it does not purchase or renew monthly plans.

## More ordinary instance operations

| Task | CLI command |
| --- | --- |
| Boot a stopped PAYG instance without GPUs | `autodl instance power-on INSTANCE_UUID --no-gpu` |
| Read current CPU, RAM, GPU count, and disk usage | `autodl instance monitor INSTANCE_UUID` |
| Change the display name | `autodl instance rename INSTANCE_UUID 'My experiment'` |
| Restore the system disk from the configured image | `autodl instance reset INSTANCE_UUID --yes` |
| Schedule shutdown in AutoDL | `autodl instance shutdown-at INSTANCE_UUID '2027-01-01T20:30+08:00'` |
| Cancel the shutdown timer | `autodl instance cancel-shutdown INSTANCE_UUID` |
| Quote 50 GiB of additional data disk | `autodl instance disk-quote INSTANCE_UUID --add-gib 50` |
| Add 50 GiB to the data disk | `autodl instance disk-grow INSTANCE_UUID --add-gib 50` |

No-GPU mode still incurs a charge. The command requests that mode explicitly
and reports a provider rejection without retrying with a GPU. Shutdown times
need an explicit UTC offset. Pass your own future time in place of the example.
Disk expansion can require a restart before the new capacity appears.

### Reset an instance

Stop the instance and check its exact UUID and status with `autodl instance
list`. Reset restores the configured image and erases changes on the system
disk. AutoDL preserves the separate data disk at `/root/autodl-tmp`. See
[AutoDL's reset documentation](https://api.autodl.com/docs/reset_instance/).

The CLI requires `--yes`. In MCP, use `autodl_instance_reset` with `yes: true`
only after the user authorizes resetting that UUID. After the request is
accepted, check `instance list` for completion before starting the instance.

### Clone an instance

Stop the source first. Select a compatible machine in the same region from
`autodl --json gpu machines`. Use the same options for preview and submission:

```bash
autodl instance clone-plan SOURCE_UUID --machine-id DEST_MACHINE_ID --gpu-num 1 --copy-data-disk
autodl instance clone SOURCE_UUID --machine-id DEST_MACHINE_ID --gpu-num 1 --copy-data-disk
```

Cloning copies the system disk to a new PAYG instance. `--copy-data-disk`
also copies the data disk. `--data-disk` sets the destination's extra disk in
GiB. When copying the data disk, it defaults to the source's extra capacity.
The preview shows the requested order and the provider's destination price
estimate. It does not reserve capacity. The clone returns the new UUID when
accepted. Poll `instance list` to follow its progress. If a request times out,
check for the destination before repeating it.

These features use the ordinary AutoDL web console and are tested offline
against request shapes observed in its frontend. [No-GPU mode](https://www.autodl.com/docs/save_money/)
and [same-region cloning](https://api.autodl.com/docs/migrate_instance_2/)
are described in AutoDL's guides.

## Upgrade an existing installation

Download the new release and run `bash install.sh` again. Existing 0.2–0.6
installer deployments upgrade in place and reuse the saved session. Fresh
deployments use `~/.local/share/autodl/venv`; older deployments keep their
existing venv path. Existing `autodl-classic` command aliases remain available.

`AUTODL_AGENT_INSTALL_ROOT` and `AUTODL_AGENT_BIN_DIR` override installation
paths. Legacy `AUTODL_CLASSIC_*` overrides are still accepted. Unrelated
executables are never overwritten by the installer.

`bash uninstall-old.sh` removes only the recognized original Art installation;
it is unnecessary for ordinary version upgrades. If an MCP entry still uses
the old server name, remove that specific duplicate and register `autodl`.

## Development and releases

See [CONTRIBUTING.md](CONTRIBUTING.md), [the changelog](CHANGELOG.md), and
[release instructions](docs/RELEASING.md). Tests cover mocked API contracts,
session handling, actual stdio MCP discovery, and the iPad JavaScript fixture.
They do not rent GPUs or use a real account. The Safari login flow has been
confirmed by the original user; CI does not exercise live account operations.

MIT licensed. Backend attribution and pinned versions are documented in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). AutoDL is a third-party service;
this project is not affiliated with or endorsed by its operator.
