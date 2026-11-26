# Changelog

## 0.8.0

- Add `autodl-desktop-login` for Windows and Ubuntu. It signs in through a
  fresh browser and verifies and saves the session locally or on an explicitly
  selected Ubuntu SSH host.
- Document desktop installation, interactive sign-in, and SSH session transfer.

## 0.7.0

- Add `instance reset` and `autodl_instance_reset` for restoring the system
  disk of an ordinary instance from its configured image. Both require
  explicit confirmation and check the instance's state before submission.

## 0.6.0

- Start stopped pay-as-you-go instances in no-GPU mode with `power-on --no-gpu`.
- Clone stopped instances onto an explicit destination machine. Preview the
  request and target pricing first, and optionally copy the source data disk.
- Read live usage, rename instances, schedule or cancel shutdown, and quote or
  add data disk capacity.
- Keep usage and order previews available in read-only MCP mode. Changes to
  instances or billing require `--allow-writes`.

## 0.5.0

- Standalone public package for ordinary AutoDL GPU rentals.
- Versioned wheel, Python source distribution, installer archive, and SHA-256 checksums.
- Codex CLI and Claude Code registration instructions and configuration examples.
- GitHub CI and a release workflow that tests and builds before publishing assets.
- Retains the working 0.4.0 CLI/MCP behavior, saved-session compatibility,
  iPad Safari login, legacy command aliases, and read-only MCP default.

## 0.4.0

- Renamed the app to `autodl` and `autodl-mcp`.
- Made iPad Safari session import the default login method.
- Added the Safari Shortcut script and bounded session verification.

## 0.3.0

- Added optional browser login and recognized original-install cleanup.

## 0.2.0

- Added ordinary GPU rental support through the pinned web-console backend.
- Added focused MCP tools, offline rental previews, and credential filtering.
