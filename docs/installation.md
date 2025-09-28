# Installation

## Prerequisites

- Python 3.10 or higher is required. Earlier versions may work but are not officially supported.
- This project contains additional optional features. Using an installation command without [...] will not install them.

## Virtual Environment

It is recommended to use a virtual environment for isolation:

```bash
python -m venv .venv
```
Activate the venv before installation and before use.
```bash
source .venv/bin/activate  # On Unix-like systems
# Or on Windows: .venv\Scripts\activate
```

## Install from PyPI

For basic functionality:

```bash
pip install p2p-copy
```

With encryption support:

```bash
pip install "p2p-copy[security]"
```

This installs dependencies like `argon2-cffi` and `cryptography` for security features. See [Security](./security.md) for details.

## Development Installation

Clone the repository and install in editable mode:

```bash
git clone https://github.com/AfuLD/p2p-copy.git
cd p2p-copy
pip install -e ".[dev,security]"
```

This includes tools for testing (e.g., pytest) and documentation (e.g., MkDocs).

## Relay Server Dependencies

The relay server requires no additional packages beyond the base installation. For TLS support, obtain certificates (e.g., via Let's Encrypt). See [Relay Setup](./relay.md) for configuration.

For usage after installation, see [Usage](./usage.md). If issues arise, consult [Troubleshooting](./troubleshooting.md).
