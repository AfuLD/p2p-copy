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
