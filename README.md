# p2p-copy (Lean Phase 1)

Minimal Python library + CLI skeleton for WSS-based, chunked file transfer.

## Install (editable, dev)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,compression,security]"
```

## Run CLI
```bash
p2p-copy --help
p2p-copy send --server wss://example.org --code ABC --files README.md
p2p-copy receive --server wss://example.org --code ABC --out ./downloads
```

## Build (optional)

creates wheel and source tar ball

```bash
pip install build
python -m build
```


## Run tests
```bash
pytest tests
```

