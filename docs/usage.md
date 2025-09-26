# Usage

## Overview

`p2p-copy` uses a relay server to pair sender and receiver via a shared passphrase/code. The relay forwards data without storing it. Workflow:

1. Start the relay (on a server or test on localhost).
2. Sender: Run `send` with files/directories.
3. Receiver: Run `receive` in the output dir.

Both sender/receiver connect to the relay using the same code for pairing (one sender + one receiver per code).

## CLI Commands

### p2p-copy send

Send files/directories to a receiver.

```bash
p2p-copy send <server> <code> <files_or_dirs> [OPTIONS]
```

**Arguments**:
- `<server>`: Relay URL (e.g., `ws://localhost:8765` or `wss://relay.example:443`).
- `<code>`: Shared passphrase for pairing (hashed internally).
- `<files_or_dirs>`: One or more files/directories to send (recursive for dirs).

**Options**:
- `--encrypt`: Enable E2EE (requires `[security]` install).
- `--compress <MODE>`: Compression mode (`auto` | `on` | `off`; default: `auto`).
- `--resume`: Enable resume (skip complete/append partial files).

**Examples**:
```bash
# Send a file without extras
p2p-copy send ws://localhost:8765 mycode file.txt

# Send dir with encryption and resume
p2p-copy send wss://relay.example:443 mycode /path/to/dir --encrypt --resume

# Send multiple files with always-on compression
p2p-copy send ws://localhost:8765 mycode *.log --compress on
```

### p2p-copy receive

Receive files into a directory.

```bash
p2p-copy receive <server> <code> [OPTIONS]
```

**Arguments**:
- `<server>`: Relay URL (same as sender).
- `<code>`: Shared passphrase (must match sender).

**Options**:
- `--encrypt`: Enable decryption (must match sender).
- `--out <DIR>`: Output directory (default: `.`).

**Examples**:
```bash
# Receive to current dir
p2p-copy receive ws://localhost:8765 mycode

# Receive to custom dir with en-/decryption
p2p-copy receive wss://relay.example:443 mycode --out ./downloads --encrypt
```

### p2p-copy run-relay-server

Run the relay server.

```bash
p2p-copy run-relay-server <host> <port> [OPTIONS]
```

**Arguments**:
- `<host>`: Bind host (e.g., `localhost` or `0.0.0.0`).
- `<port>`: Bind port (e.g., `8765` or `443`).

**Options**:
- `--tls` / `--no-tls`: Enable/disable TLS (default: on).
- `--certfile <PATH>`: TLS cert PEM file.
- `--keyfile <PATH>`: TLS key PEM file.

**Examples**:
```bash
# Dev relay (no TLS)
p2p-copy run-relay-server localhost 8765 --no-tls

# Prod relay (TLS)
# Note: wss:// requires TLS-certificate, port 443 requires elevated privileges 
p2p-copy run-relay-server 0.0.0.0 443 --tls --certfile cert.pem --keyfile key.pem
```
## Typical flow (3 terminals)

```bash
# Start relay 
p2p-copy run-relay-server localhost 8765 --no-tls
```

```bash
# Receiver (waiting)
p2p-copy receive ws://localhost:8765 demo --out ./downloads
```

```bash
# Sender
echo "hello test" > cli_sample.txt # creates test file
p2p-copy send ws://localhost:8765 demo cli_sample.txt
rm cli_sample.txt # removes test file 
```

### Results:
- ./downloads/cli_sample.txt contains the file sent. 
- send and receive exit without error
- relay stays open until closed
---

## Pairing and Transfer

- **Pairing**: Sender/receiver send hello with code hash. Relay pairs and forwards unchanged messages.
- **Timing**: Relay needs to be started first. Sender and Receiver may connect in random order.
- **Manifest**: Sender sends file list; receiver replies with existing file states if `--resume` is used.
- **Transfer**: Files streamed in 1 MiB chunks with a chained checksum to ensure integrity. 
- **Errors**: Non-zero exit code on mismatch/timeout.

For advanced: See [Features](features.md) and [Troubleshooting](troubleshooting.md).
