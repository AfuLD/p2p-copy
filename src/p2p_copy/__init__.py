from importlib.metadata import version as _v

import sys

if hasattr(sys.stdout, "reconfigure"):  # on Python >= 3.7
    sys.stdout.reconfigure(line_buffering=True)

__all__ = ["__version__", "send", "receive", "CompressMode"]
try:
    __version__ = _v("p2p-copy")
except Exception:
    __version__ = "0.0.0"

# re-export
from .api import send, receive
from .compressor import CompressMode
