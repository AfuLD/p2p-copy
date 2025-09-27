# Installation

## Prerequisites

- Python 3.10 or higher. (Older version will probably but not definitely work as well.) 
- For E2E-encryption support: Install the `security` extras on client machines.

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

For running the relay with TLS:
- Have or acquire trusted certs (e.g. with Let's Encrypt).


See [Relay Setup](relay.md) for details.
