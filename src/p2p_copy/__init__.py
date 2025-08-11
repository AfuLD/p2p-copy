from importlib.metadata import version as _v

__all__ = ["__version__", "send", "receive"]
try:
    __version__ = _v("p2p-copy")
except Exception:
    __version__ = "0.0.0"

from .api import send, receive  # re-export
