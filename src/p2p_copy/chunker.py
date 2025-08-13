from typing import Iterator, BinaryIO

CHUNK_SIZE = 1 << 20  # 1 MiB

def read_in_chunks(fp: BinaryIO) -> Iterator[bytes]:
    while True:
        b = fp.read(CHUNK_SIZE)
        if not b:
            break
        yield b
