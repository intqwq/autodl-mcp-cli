# Security

Never post AutoDL sessions, passwords, SSH credentials, or private API responses
in public issues. A Safari session export grants account access. Store it only
through the local authentication prompt, and keep the config file private.

MCP masks instance credentials by default and excludes authentication, config,
raw request tools, and generic command execution. `--allow-writes` and
`--allow-secrets` explicitly expand what its tools can do or return. These
controls do not isolate an agent that already has shell access as your Unix user.

For a suspected vulnerability, use GitHub's **Report a vulnerability** option
if available. Otherwise open an issue containing only a high-level description
and ask for a private reporting channel before sharing sensitive details.

The tool relies on unofficial service endpoints. An accepted API request is
not proof of a completed state change. Reconcile instance state after failures
and never blindly retry a rental creation request.
