from __future__ import annotations
from typing import Iterator, BinaryIO

CHUNK_SIZE = 1 << 20  # 1 MiB

def read_in_chunks(fp: BinaryIO, *, chunk_size: int = CHUNK_SIZE) -> Iterator[bytes]:
    """reads in bytes from a file in chunks, starts at current file position"""
    while True:
        b = fp.read(chunk_size)
        if not b:
            break
        yield b
