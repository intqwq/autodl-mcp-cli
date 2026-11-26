# Third-party dependencies

This project extends separately installed packages; their licenses and notices
remain applicable. Upstream source is not bundled in this repository.

| Package | Pinned version | Purpose |
| --- | --- | --- |
| [autodl-cli](https://github.com/KrisTHL181/autodl-cli) | 0.1.0 | Web-console API client and rental commands |
| [click2mcp](https://pypi.org/project/click2mcp/) | 0.1.0 | Focused typed tools from Click commands |
| [mcp](https://pypi.org/project/mcp/) | 2.3.0 | MCP client/server protocol |
| [httpx](https://www.python-httpx.org/) | 0.28.1, SOCKS extra | HTTP transport |
| [playwright](https://playwright.dev/python/) | 1.62.0, optional | Optional server-browser login |

The MIT-licensed `autodl-cli` backend is by **KrisTHL181**. Reviewed upstream
wheel SHA-256:

```text
32778974f4263ad5ccb1e69dff654a1d492b4e223d896db3a9d8edba491056a5
```

Direct runtime versions are pinned. Transitive dependencies can vary by Python
version and platform. The application does not vendor or claim authorship of
those dependencies. AutoDL service names and trademarks belong to their owners.
