# Module Layout

This page outlines the package structure and key modules of `p2p_copy`. The project uses a src-layout for packaging. For API details, see [API](./api.md).

## Project Structure

```
p2p-copy/                      # Root
├── src/                       # Installable packages
│   ├── p2p_copy/
│   │   ├── __init__.py        # Package init, re-exports public API
│   │   ├── api.py             # Core async functions: send(), receive()
│   │   ├── compressor.py      # Compression handling (Zstd)
│   │   ├── io_utils.py        # File I/O, manifest iteration, checksums
│   │   ├── protocol.py        # Data classes, framing, control messages
│   │   └── security.py        # Encryption (AES-GCM), hashing (Argon2)
│   ├── p2p_copy_cli/
│   │   └── main.py            # Typer CLI app (send, receive, run-relay-server)
│   └── p2p_copy_server/
│       ├── __init__.py        # Re-exports run_relay
│       └── relay.py           # WebSocket server logic
├── docs/                      # Documentation (MkDocs source)
│   ├── index.md
│   ├── installation.md
│   └── ...                    # Other .md files
├── examples/                  # Usage examples/scripts
├── tests/                     # Tests of specific and all functionality
├── pyproject.toml             # Build/config
├── README.md
└── LICENSE
```

## Key Modules

### p2p_copy
Main library package. Installs as `p2p_copy`.

- **`__init__.py`**: Defines `__version__`, re-exports `send`, `receive`, `CompressMode`.
- **`api.py`**: High-level async APIs for sending/receiving. Handles connections, transfers, and feature logic.
- **`compressor.py`**: `Compressor` class for per-file Zstd compression (auto/on/off modes).
- **`io_utils.py`**: Utilities for async file reading (`read_in_chunks`), checksum computation (`compute_chain_up_to`), manifest building (`iter_manifest_entries`).
- **`protocol.py`**: Protocol definitions: dataclasses (`Hello`, `Manifest`), framing (`pack_chunk`/`unpack_chunk`), constants (e.g., `READY`, `EOF`).
- **`security.py`**: `ChainedChecksum` for integrity, `SecurityHandler` for end-to-end encryption.

### p2p_copy_cli
CLI entrypoint package.

- **`main.py`**: Typer app with commands (`send`, `receive`, `run-relay-server`).

### p2p_copy_server
Standalone relay package.

- **`__init__.py`**: Re-exports `run_relay`.
- **`relay.py`**: Async WebSocket server: pairing logic, bidirectional piping, TLS support.

## Non-Installable Folders

- **`docs/`**: MkDocs Markdown sources; build with `mkdocs build`.
- **`examples/`**: Runnable scripts/demos.
- **`tests/`**: Pytest suite; run with `pytest`.

For installation, see [Installation](./installation.md). For troubleshooting contributions, see [Troubleshooting](./troubleshooting.md).