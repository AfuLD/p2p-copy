from typing import Iterator, BinaryIO

def read_in_chunks(fp: BinaryIO, chunk_size: int) -> Iterator[bytes]:
    while True:
        b = fp.read(chunk_size)
        if not b:
            break
        yield b
