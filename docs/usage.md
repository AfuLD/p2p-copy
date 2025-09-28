# Usage

## Overview

p2p-copy facilitates file transfers via a WebSocket relay. The workflow involves starting a relay server, then running sender and receiver clients with a shared code for pairing. The relay forwards data without storage, supporting multiple client pairs.
                
For protocol details, see [Features](./features.md). For API usage in scripts, see [API](./api.md) and [APIExamples](./examples.md).


## Get usage info in terminal
```bash
p2p-copy --help
p2p-copy send --help
p2p-copy receive --help
p2p-copy run-relay-server --help
```

## CLI Commands

The CLI is built with Typer and provides three main commands: `send`, `receive`, and `run-relay-server`.

### p2p-copy send

Transfers files or directories to a receiver.

```bash
p2p-copy send <server> <code> <files_or_dirs> [OPTIONS]
```

**Arguments**:
- `<server>`: Relay URL (e.g., `ws://localhost:8765` or `wss://relay.example:443`).
- `<code>`: Shared passphrase for pairing (hashed internally).
- `<files_or_dirs>`: Files or directories to send (recursive for directories).

**Options**:
- `--encrypt`: Enable end-to-end encryption (requires `[security]` install).
- `--compress <MODE>`: Compression mode (`auto`, `on`, or `off`; default: `auto`).
- `--resume`: Enable resume (skip complete files and append partial ones).

**Examples**:
```bash
# Basic file transfer
p2p-copy send ws://localhost:8765 mycode file.txt

# Directory with encryption and resume
p2p-copy send wss://relay.example:443 mycode /path/to/dir --encrypt --resume

# Multiple files with forced compression
p2p-copy send ws://localhost:8765 mycode *.log --compress on
```

### p2p-copy receive

Receives files into a specified directory.

```bash
p2p-copy receive <server> <code> [OPTIONS]
```

**Arguments**:
- `<server>`: Relay URL (same as sender).
- `<code>`: Shared passphrase (must match sender).

**Options**:
- `--encrypt`: Enable decryption (must match sender).
- `--out <DIR>`: Output directory (default: current directory).

**Examples**:
```bash
# Receive to current directory
p2p-copy receive ws://localhost:8765 mycode

# Receive to custom directory with encryption
p2p-copy receive wss://relay.example:443 mycode --out ./downloads --encrypt
```

### p2p-copy run-relay-server

Starts the relay server.

```bash
p2p-copy run-relay-server <host> <port> [OPTIONS]
```

**Arguments**:
- `<host>`: Bind host (e.g., `localhost` or `0.0.0.0`).
- `<port>`: Bind port (e.g., `8765` or `443`).

**Options**:
- `--tls` / `--no-tls`: Enable/disable TLS (default: enabled).
- `--certfile <PATH>`: TLS certificate PEM file.
- `--keyfile <PATH>`: TLS private key PEM file.

**Examples**:
```bash
# Development relay without TLS
p2p-copy run-relay-server localhost 8765 --no-tls

# Production relay with TLS
p2p-copy run-relay-server 0.0.0.0 443 --tls --certfile cert.pem --keyfile key.pem
```

## Typical Workflow

1. Start the relay (see [Relay Setup](./relay.md)).
2. Run the receiver (it waits for the sender).
3. Run the sender with matching code and server URL.

Example in three terminals:

```bash
# Terminal 1: Relay
p2p-copy run-relay-server localhost 8765 --no-tls
```

```bash
# Terminal 2: Receiver
p2p-copy receive ws://localhost:8765 demo --out ./downloads
```

```bash
# Terminal 3: Sender
echo "hello test" > sample.txt
p2p-copy send ws://localhost:8765 demo sample.txt
rm sample.txt
```

The receiver saves `sample.txt` in `./downloads`. Both clients exit on completion; the relay persists.

## Notes

- Pairing occurs via code hash. Start the relay first; sender and receiver order is flexible.
- Errors result in non-zero exit codes (e.g., timeouts, mismatches).
- For security considerations, see [Security](./security.md). For issues, see [Troubleshooting](./troubleshooting.md).
