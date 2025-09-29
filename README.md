# p2p-copy

[![PyPI version](https://badge.fury.io/py/p2p-copy.svg)](https://badge.fury.io/py/p2p-copy)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-online-brightgreen.svg)](https://afuld.github.io/p2p-copy)

p2p-copy is a Python library and command-line tool for transferring files and directories over a WebSocket relay server. It supports chunked streaming, optional end-to-end encryption, compression, and resume functionality, making it suitable for environments with restrictive firewalls, such as high-performance computing (HPC) systems. The tool avoids dependencies on SSH or inbound ports, relying instead on outbound connections over ports like 443.

The design prioritizes performance, low resource usage, and simplicity, with a stateless relay that forwards data without storage. For details on the protocol and internals, see [Features](docs/features.md).

## Full Documentation
For detailed guides, visit the [full documentation site](https://afuld.github.io/p2p-copy).

## Quickstart

Install via pip:
```bash
pip install p2p-copy[security]
```

### Run Relay (one terminal)
```bash
p2p-copy run-relay-server localhost 8765 --no-tls  # For development
# Or with TLS: --tls --certfile cert.pem --keyfile key.pem
```

### Send Files (another terminal)
```bash
p2p-copy send ws://localhost:8765 mysecretcode /path/to/files_or_dirs --encrypt --compress on --resume
```

### Receive (third terminal)
```bash
p2p-copy receive ws://localhost:8765 mysecretcode --out ./downloads --encrypt
```

Use the same `mysecretcode` for sender and receiver pairing. For full CLI details, see [Usage](docs/usage.md). For production relay setup, see [Relay Setup](docs/relay.md).

## Key Aspects

- **Pairing and Transfer**: Clients connect to a relay using a shared code (hashed for security). Files are streamed in chunks with integrity checks.
- **Optional Features**: End-to-end encryption (AES-GCM with Argon2-derived keys), per-file compression (Zstandard), and the option to resume partial transfers.
- **Use Cases**: Designed for HPC workflows where traditional tools like SCP or rsync are limited by firewalls or configuration requirements.
- **API Integration**: Embeddable in Python scripts; see [API](docs/api.md).

For installation instructions, see [Installation](docs/installation.md). For module structure, see [Module Layout](docs/layout.md).
