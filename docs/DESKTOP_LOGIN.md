# AutoDL desktop login manual

Use a Windows or Ubuntu computer with a graphical desktop and Python 3.11 or
newer. The script opens a fresh Chromium profile at AutoDL's login page.
Enter your credentials and complete any verification in the browser. Once
AutoDL signs you in, the script closes Chromium and verifies and saves your
session. The script prints the result and configuration path.

## Windows PowerShell

From the extracted release directory or a Git checkout of this repository:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[login]"
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\autodl-desktop-login.exe
.\.venv\Scripts\autodl.exe --json account me
```

For local CLI use, the session is stored under your Windows user profile at
`%USERPROFILE%\.autodl-cli\config.toml` by default. Keep this file in a
directory private to your user account. Use the SSH option below if Codex runs
on an Ubuntu server.

## Ubuntu desktop

From the extracted release directory or a Git checkout of this repository:

```bash
bash install.sh --with-browser
~/.local/bin/autodl-desktop-login
~/.local/bin/autodl --json account me
```

The session is stored in `~/.autodl-cli/config.toml` by default. Run the CLI
and MCP server as the same user. Set `AUTODL_CLI_HOME` if the installation
already uses a different private configuration directory.

## Sign in for a remote Ubuntu host

Install the AutoDL CLI on your Ubuntu host first. Use the SSH account that runs
Codex or the MCP server. Check that you can connect from your desktop with
`ssh USER@HOST`, substituting your SSH username and hostname. You can also
use a configured SSH host alias.

**Windows PowerShell**

```powershell
.\.venv\Scripts\autodl-desktop-login.exe --ssh USER@HOST
```

**Ubuntu desktop**

```bash
~/.local/bin/autodl-desktop-login --ssh USER@HOST
```

After sign-in, the script streams the new session over SSH to
`autodl auth import` on the Ubuntu host. The host verifies it with AutoDL
before saving it. Any previous local session remains available on your
desktop. Check the remote login with:

```bash
ssh USER@HOST '~/.local/bin/autodl --json account me'
```

## Manual sign-in and transfer

To open the same sign-in flow directly through the CLI, use
`autodl auth login --browser`. On Windows, run
`.\.venv\Scripts\autodl.exe auth login --browser`. Complete sign-in in
the browser. This saves an AutoDL session locally.

To transfer an already saved session to your Ubuntu host, pipe it directly to
the remote import command. The JSON contains a login secret. Keep it in the
pipe and out of files, chat, and logs.

**Windows PowerShell**

```powershell
.\.venv\Scripts\autodl.exe auth export | ssh -T USER@HOST '~/.local/bin/autodl auth import'
```

**Ubuntu**

```bash
~/.local/bin/autodl auth export | ssh -T USER@HOST '~/.local/bin/autodl auth import'
```

## Troubleshooting

- For slow sign-in or SMS verification, pass `--timeout 300` to give yourself
  five minutes in the browser.
- If Chromium is missing on Windows, rerun the Playwright installation
  command above. For an installed Chromium or Chrome executable, pass
  `--browser-path` with its full path.
- If SSH import fails, check the remote account, AutoDL installation, and
  outbound HTTPS access. The remote import preserves the existing session when
  verification fails.
- For an iPad or a headless host with no Windows or Ubuntu desktop available,
  follow the [iPad Safari Shortcut guide](../IPAD_LOGIN.md).
