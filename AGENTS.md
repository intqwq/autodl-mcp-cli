# Classic AutoDL rental operations

Use `autodl --json ...` or the `autodl` MCP server. This is for
ordinary GPU rentals, using the web-console session. Never substitute an Art
application or Pro instance. Never ask for credentials in chat.

1. Read `account balance`, `gpu find MODEL -a`, `gpu machines`, `image list`,
   and `instance list` to establish inventory and existing resources.
2. Exact GPU names and machine/image IDs must come from actual query results.
   The pinned upstream CLI's JSON money fields are raw thousandths of yuan;
   verify price per GPU versus total instance price and additional storage.
3. Respect the user's authorized GPU count, budget and runtime. Use the
   provider-side `instance shutdown-at` timer when authorized. The tool has no
   spending cap or background watchdog.
4. Use `autodl plan --machine-id ID --image ID` or
   `plan_rental` to inspect a validated creation request offline.
5. Prefer an explicit selected machine ID for rental creation. A stock listing
   can become stale before checkout. Failed/uncertain orders require checking
   `instance list` before another order; do not run competing create requests.
6. Startup and shutdown requests are asynchronous. Poll `instance list` and
   match the exact UUID; `instance detail` describes configuration, not status.
7. Stop interrupts the workload; release deletes the instance and its data.
   Preserve needed data and follow the user's instructions before releasing.
8. The developer token used for the official Pro/Art APIs is not this tool's
   login flow. Expired sessions require the user to sign in normally in iPad Safari and
   import the session using the provided Shortcut and `autodl auth login`.
   The default flow requires no Chromium or desktop on the server. Do not ask for account passwords or session exports in chat.
9. Use SSH separately for executing experiments and transferring results.
   Do not store secrets in project files, prompts or logs.
10. Start with `instance monitor` to inspect usage. For CPU-only boot, request
    `instance power-on --no-gpu` explicitly and verify `start_mode` in the list.
11. Clone a stopped source onto an explicitly selected compatible machine.
    Run `instance clone-plan` before ordering and confirm whether to copy the
    data disk. A clone creates a separate billable instance. Use `instance
    disk-quote` before `disk-grow` and account for ongoing storage charges.
12. Use `instance rename` to change an instance's display name. System reset
    erases changes on the system disk. Only use `instance reset --yes` or
    `autodl_instance_reset` with `yes: true` when the user authorized resetting
    that exact instance. Verify the UUID and shutdown status first, then poll
    `instance list` after submission.

For MCP, set `json=true` on generated tools. Writes exist only when the operator
starts `autodl-mcp --allow-writes`. Auth, config, debugging/raw-request
commands and generic command escape hatches are excluded from MCP.
