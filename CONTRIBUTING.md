# Contributing

Use Python 3.11+ and keep development inside a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
```

Node.js enables the Safari JavaScript fixture tests; those tests are skipped
when Node is unavailable. The default suite never signs in or rents GPUs.
Use fake credentials and mocked responses for tests and issue reports.

Preserve the boundary between ordinary rentals and Art/Pro products. Maintain
read-only MCP defaults, explicit mutation opt-in, local authentication, and
reconciliation after an uncertain mutation. Do not add automatic order retries.

Discuss changes to endpoint contracts in an issue. Do not include account
session exports, passwords, full API responses, or private machine data.
See [SECURITY.md](SECURITY.md) for handling security reports.

To publish, follow [docs/RELEASING.md](docs/RELEASING.md).
