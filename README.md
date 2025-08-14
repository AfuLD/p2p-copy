# p2p-copy (in development)

Minimal Python library + CLI skeleton for WSS-based, chunked file transfer.

## General installation info
Create a virtual environment (if not already created):
```bash
python -m venv .venv
```
Activate the venv before installation and before use 
```bash
source .venv/bin/activate
```

This project contains additional optional features  
Using an installation command without [...] will not install them


## Install from git (editable)
Clone repository first
```bash
git clone https://github.com/AfuLD/p2p-copy.git p2p-copy
cd p2p-copy
```
```bash
pip install --editable ".[dev,compression,security]"
```


## Install from wheel or tar ball 
Exact file name may change
```bash
pip install "p2p_copy-0.1.0a0-py3-none-any.whl[dev,compression,security]"
```
or
```bash
pip install "p2p_copy-0.1.0a0.tar.gz[dev,compression,security]"
```


## Install from PyPI (once available)
```bash
pip install "p2p-copy[compression,security]" 
```


## Run CLI
```bash
p2p-copy --help
p2p-copy send --help
p2p-copy receive --help
p2p-copy run-relay-server --help
```


## Run tests 
Needs dev feature installed
```bash
pytest tests
```


## Build (optional)
Creates wheel and source tar ball
```bash
pip install build
python -m build
```


# p2p-copy CLI Usage

> **Status (Phase 2):** Only the **first** specified file is transferred.
> `--encrypt`, `--compress`, `--resume` are prepared but will only be functional in later phases.

---

## Commands

### `send`

**Synopsis**

p2p-copy send SERVER CODE FILE \[FILE ...] \[OPTIONS]

Arguments (positional)

```
SERVER — Relay URL, e.g., ws://localhost:8765 (for production later wss://…:443)

CODE — shared password/code for pairing

FILE — one or more files (Phase 2: only the first is sent)
```

Options

```
--encrypt, -e — enable end-to-end encryption (reserved)

--compress {auto,on,off} — compression mode (reserved)

--resume / --no-resume — resume transfer (reserved)

--help — show help
```

Examples

```bash
# Local, minimal
p2p-copy send ws://localhost:8765 demo sample.txt

# Multiple files (Phase 2: only sample.txt will be sent)
p2p-copy send ws://localhost:8765 demo sample.txt notes.md

# With (future) features
p2p-copy send ws://localhost:8765 demo sample.txt --encrypt --compress on --resume
```

---

### `receive`

**Synopsis**

p2p-copy receive SERVER CODE \[--out DIR] \[OPTIONS]

Arguments (positional)

```
SERVER — Relay URL, e.g., ws://localhost:8765

CODE — shared password/code for pairing
```

Options

```
--out, -o DIR — target directory (default: current directory)

--resume / --no-resume — resume (reserved)

--help — show help
```

Examples

```bash
# Receive to /downloads
p2p-copy receive ws://localhost:8765 demo --out ../downloads

# Receive to current directory
p2p-copy receive ws://localhost:8765 demo
```

---

### `run-relay-server`

**Synopsis**

p2p-copy run-relay-server HOST PORT \[--tls/--no-tls] \[--certfile PATH] \[--keyfile PATH]

Arguments

```
HOST — interface, e.g., localhost or 0.0.0.0

PORT — port to use, e.g., 8765 or 443
```

Options

```
--tls/--no-tls — use TLS (WSS). Default: -tls is used

--certfile PATH, --keyfile PATH — required when --tls is set

--help — show help
```

Examples

```bash
# Local relay (without TLS)
p2p-copy run-relay-server localhost 8765 --no-tls

# # With TLS (certificate + key required)
p2p-copy run-relay-server 0.0.0.0 443 --certfile /etc/ssl/certs/fullchain.pem --keyfile /etc/ssl/private/privkey.pem
```

---

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
echo "hello test" > sample.txt # creates test file
p2p-copy send ws://localhost:8765 demo sample.txt
rm sample.txt # removes test file 
```

Result: downloads/sample.txt contains the sent content.

---

## Notes

```
For local tests use ws://localhost:8765; WSS on 443 will follow later (requires privileges and TLS).

The receiver has no --encrypt/--compress flags; the sender decides (the protocol will negotiate that later).

chunk_size is internal and not configurable via the CLI.
```
