import sys

if hasattr(sys.stdout, "reconfigure"):  # on Python >= 3.7
    sys.stdout.reconfigure(line_buffering=True)

__all__ = ["run_relay"]

from .relay import run_relay
