# p2p-copy

[![PyPI version](https://badge.fury.io/py/p2p-copy.svg)](https://badge.fury.io/py/p2p-copy)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A secure, file transfer tool over a relay server. Optimized for performance with minimal setup. Avoids firewall issues and dependencies.

## Quickstart

Install via pip:
```bash
pip install p2p-copy[security]
```

### Run Relay (one terminal)
```bash
p2p-copy run-relay-server localhost 8765 --no-tls  # Dev
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

Share the same `mysecretcode` between sender/receiver for pairing.

## Features

- **Easy Pairing**: One sender + one receiver per code, no keys needed.
- **Chunked Streaming**: no full-file buffering, low RAM-usage.
- **Resume**: Skip already existing and append partial files via checksums.
- **E2EE**: AES-GCM with Argon2-derived keys (optional deps).
- **Compression**: Zstd, auto per-file based on ratio.
- **Security**: Hashed codes, TLS on relay.

See [Features](features.md) for details.

## Why p2p-copy?

- Firewall-friendly (WSS on 443).
- No central storage; relay just forwards.
- Performance optimized
- Lightweight, secure, open-source, easy to use.

## Installation

See [Installation](installation.md).

## Usage

See [Usage](usage.md).

## API

See [API](api.md).

---

Built with [MkDocs](https://www.mkdocs.org) & [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).

