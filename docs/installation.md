# Installation

## Prerequisites

- Python 3.10 or higher. (Older version will probably but not definitely work as well.)
- This project contains additional optional features.  
- Using an installation command without [...] will not install them.
- For E2E-encryption support: Install the `security` extras on client machines.


## General installation info
Create a virtual environment (if not already created):
```bash
python -m venv .venv
```
Activate the venv before installation and before use.
```bash
source .venv/bin/activate
```

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
