
from __future__ import annotations

import hashlib


class ChainedChecksum:
    """chained checksum over a byte stream"""

    def __init__(self, seed: bytes = b"") -> None:
        self.prev_chain = seed

    def next_hash(self, payload: bytes) -> bytes:
        h = hashlib.sha256()
        h.update(self.prev_chain)
        h.update(payload)
        self.prev_chain = h.digest()
        return self.prev_chain
