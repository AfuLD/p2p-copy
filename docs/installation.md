# Installation

## Prerequisites

- Python 3.10 or higher. (Older version will probably but not definitely work as well.) 
- For encryption support: Install the `security` extras (requires `cryptography` and `argon2-cffi`).

## Install from PyPI

```bash
pip install p2p-copy
```

With encryption support:
```bash
pip install "p2p-copy[security]"
```

## Development Installation

Clone the repository and install in editable mode:
```bash
git clone https://github.com/AfuLD/p2p-copy.git
cd p2p-copy
pip install -e ".[dev,security]"
```

This includes testing and documentation tools.

## Relay Server Dependencies

For running the relay with TLS either:
- Generate self-signed certs (dev)
- Have or acquire trusted certs (e.g. with Let's Encrypt) (prod).


See [Relay Setup](relay.md) for details.
