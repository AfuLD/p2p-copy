# Features

`p2p_copy` is a fast, firewall-friendly file transfer tool built around WebSockets. It pairs one sender and one receiver through a lightweight relay, streams files in chunks (optionally compressed and end-to-end encrypted), and can resume interrupted transfers. The CLI is backed by a small Python API, so you can script it or embed it in your own programs.

---

## Highlights at a glance

* **Firewall-friendly over WS/WSS (Port 443):** Clients connect outwards to a relay (no inbound rules). The relay simply pairs connections and pipes frames; it does not persist data.
* **Simple pairing with a shared code:** A sender and a receiver meet via a code-derived hash announced in an initial `hello` frame. Matched peers are piped together, and the sender gets a `ready`.
* **Chunked streaming with integrity:** Files are transmitted as binary frames `[seq | chain | payload]`, where `chain = sha256(prev_chain || payload)`. Sequence and chained checksums detect loss/reordering/corruption.
* **Optional end-to-end encryption:** When enabled, metadata and content are encrypted with AES-GCM; keys/nonce chain are derived via Argon2id and a chained checksum. Transport still uses TLS when WSS is enabled.
* **Auto/on/off compression (Zstd):** Per-file decision with an initial sample; if compressed size < 95% of original, the rest of the file is sent compressed. Receiver auto-detects and decompresses.
* **Resume & skip:** Receiver reports existing byte counts and chained checksum; sender appends remaining bytes or skips identical files.
* **Clean CLI & Python API:** `typer`-based CLI (`send`, `receive`, `run-relay-server`) and importable API (`send()`, `receive()`).

---

## How it works

### 1) Pairing & relay

* **Hello handshake:** Each client sends a JSON `hello` with `code_hash_hex` and `role` (`sender`/`receiver`). The relay pairs exactly one sender with one receiver per code hash. On success, the sender receives a `ready`.
* **Lightweight piping:** After pairing, the relay just forwards frames bidirectionally and closes peers when either side ends. It disables WebSocket compression to avoid interference with app-level compression.

### 2) Manifests & metadata

* **Sender manifest:** Lists relative file paths, sizes, and whether resume is desired. Can be sent encrypted.
* **Receiver manifest (for resume):** Reports local byte count and chained checksum per path (over **raw** bytes). May be encrypted when E2EE is on.

### 3) Streaming data

* **File headers:** For each file the sender emits `file` (or `enc_file`) with `path`, `size`, compression type (`zstd`/`none`), and `append_from` if resuming.
* **Binary chunks:** Each payload is optionally compressed, optionally encrypted, and wrapped with `seq` and `chain` before sending. Receiver verifies sequence, chained checksum, decrypts, decompresses, and writes to disk asynchronously.
* **End markers:** `file_eof` closes a file; final `eof` closes the session cleanly.

---

## Security model

* **Transport:** WSS (TLS) is supported by running the relay with a cert/key. WS can be used for local/testing.
* **Pairing secret:** The user-provided code is hashed. With E2EE off, SHA-256 is used; with E2EE on, Argon2id derives both the hello hash and the AES-GCM key material.
* **E2EE (optional):**

    * AES-GCM for payloads and control messages (manifest, file headers).
    * Nonces are derived from a chained SHA-256 (`ChainedChecksum`) to avoid reuse, seeded by a random value from the encrypted manifest.
* **Integrity:** Each binary frame’s chained checksum covers the *compressed* (and, if enabled, *encrypted*) payload, and the receiver verifies it before decompression.

> **Note:** E2EE is optional to let you choose performance vs. privacy depending on your environment and trust in the relay.

---

## Compression

* **Modes:** `auto` (default), `on`, `off`.
* **Auto heuristic:** The first chunk is test-compressed with Zstd level 3; if ratio < 0.95, the file is sent compressed, otherwise uncompressed. The receiver detects the chosen mode per file.
* **WebSocket compression:** Disabled at the socket level to prevent double compression and preserve chunk framing.

---

## Resume behavior

* **Pre-flight:** If the sender requests resume, the receiver computes chained checksums of its local files (or prefixes thereof) and replies with sizes+chains.
* **Decision:** The sender validates the receiver’s reported prefix against its own chain; it either (a) skips identical files, (b) appends remaining bytes, or (c) restarts from zero on mismatch.

---

## CLI overview

```bash
# Send files/dirs
p2p-copy send wss://relay.example:443 MyCode ./data ./results --encrypt --compress auto --resume

# Receive into a directory
p2p-copy receive wss://relay.example:443 MyCode --encrypt --out ./target

# Run relay (WSS)
p2p-copy run-relay-server 0.0.0.0 443 --tls --certfile /path/cert.pem --keyfile /path/key.pem
```

The CLI is thin over the Python API (`send()`, `receive()`) and exposes the same flags.

---

## Design choices

* **Async I/O everywhere:** Disk reads/writes and network I/O use `asyncio` with `to_thread` for blocking file ops; this keeps the event loop responsive and fully utilizes bandwidth.
* **Minimal relay logic:** The relay avoids stateful storage; it pairs, pipes, and cleans up waiting slots on disconnects.
* **Structured control frames:** Small JSON controls (`hello`, `manifest`, `file`, `*_eof`) + binary data frames keep parsing simple and robust.

---

## Limitations & scope

* **One sender ↔ one receiver per code:** A code can be reused after a completed/aborted session, but not concurrently for multiple pairs.
* **No server-side storage:** The relay does not buffer entire files; very large transfers rely on the streaming pipeline end-to-end.
* **Per-file compression choice:** Compression is decided per file (not per chunk) after sampling the first chunk.

---

## API surface (Python)

* `p2p_copy.send(server, code, files, *, encrypt=False, compress=CompressMode.auto, resume=False) -> int`
* `p2p_copy.receive(server, code, *, encrypt=False, out=None) -> int`
* `p2p_copy.CompressMode` = `auto | on | off`

---

## Internals (for contributors)

* **Framing & protocol:** `protocol.py` defines JSON controls and the binary chunk header (`!Q32s`).
* **I/O helpers:** Async chunked reads, chained checksums, and manifest iteration live in `io_utils.py`.
* **Compression layer:** Zstd contexts and auto-decision logic are in `compressor.py`.
* **Security layer:** Argon2id derivation, AES-GCM wrapper, and nonce chaining in `security.py`.
* **Relay server:** Pairing logic and piping are in `p2p_copy_server/relay.py`.

---

## Why this approach

The design trades complexity for performance and robustness in real-world environments (HPC clusters, restrictive networks). By combining chunked streaming, per-file compression, deterministic integrity checks, optional E2EE, and a stateless relay, `p2p_copy` aims to be both **fast** and **practical**—from shell scripts to Python pipelines.

---

*Versioned package metadata and re-exports are provided in `__init__.py`.* 
