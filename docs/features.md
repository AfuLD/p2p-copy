# Features

p2p-copy provides file transfer via WebSockets, pairing one sender and one receiver through a relay. It supports chunked streaming, optional encryption and compression, and resume. The CLI wraps a Python API for scripting. For usage, see [Usage](./usage.md). For API, see [API](./api.md).

## Core Functionality

- **Firewall-Friendly**: Uses WS/WSS over port 443 for outbound connections, bypassing inbound restrictions common in HPC environments.
- **Pairing**: Clients share a code (hashed with SHA-256 or Argon2 for encryption). Relay matches one sender and one receiver per hash.
- **Chunked Streaming**: Transfers in 1 MiB chunks without full-file buffering, reducing memory usage.
- **Integrity Checks**: Chained SHA-256 checksums detect corruption, loss, or reordering.
- **Resume**: Skips complete files and appends partial ones using checksums (receiver reports existing data).
- **Manifest Exchange**: Sender lists files; receiver responds with local states for resume.

## Optional Enhancements

- **End-to-End Encryption**: AES-GCM with Argon2id-derived keys and chained nonces. Metadata and content encrypted; transport TLS separate. See [Security](./security.md).
- **Compression**: Zstandard (Zstd) per file. Modes: `auto` (tests first chunk for <95% ratio), `on`, or `off`. Receiver auto-decompresses.
- **Async I/O**: Uses `asyncio` for non-blocking disk and network operations, maximizing throughput.

## Protocol Overview

- **Handshake**: JSON `hello` with role and code hash. Relay pairs and sends `ready` to sender.
- **Controls**: JSON frames for manifests, file starts (`file`/`enc_file`), and ends (`file_eof`, `eof`).
- **Data Frames**: Binary `[seq | chain | payload]`, with sequence and chained checksum.
- **WebSocket Settings**: Compression disabled to avoid interference.

## Resume Mechanism

- Sender requests resume in manifest.
- Receiver computes chained checksums over raw bytes on disk.
- Sender validates prefixes: skips matches, appends partials, overwrites mismatches.

## Limitations

- server performance limits the amount of concurrent transfers
- Single pair per code; no broadcasting.
- No relay storage; transfers depend on both clients to stay connected.
- Per-file (not per-chunk) compression decisions.

## Internals

- Framing in `protocol.py`.
- I/O in `io_utils.py` (e.g., async chunk reads).
- Compression in `compressor.py`.
- Security in `security.py`.
- Relay logic in `relay.py`.

For module details, see [Module Layout](./layout.md). For setup, see [Relay Setup](./relay.md). For issues, see [Troubleshooting](./troubleshooting.md).