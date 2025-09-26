from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterator, Tuple, BinaryIO, List, AsyncIterable

from p2p_copy.security import ChainedChecksum

CHUNK_SIZE = 1 << 20  # 1 MiB


async def read_in_chunks(fp: BinaryIO, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterable[bytes]:
    """
    Asynchronously read bytes from a file in chunks.

    Parameters
    ----------
    fp : BinaryIO
        The file pointer to read from.
    chunk_size : int, optional
        Size of each chunk in bytes. Default is 1 MiB.

    Yields
    ------
    bytes
        The next chunk of data.
    """

    while True:
        # Read from disk without blocking the event-loop
        chunk = await asyncio.to_thread(fp.read, chunk_size)
        if not chunk:
            break
        yield chunk


async def compute_chain_up_to(path: Path, limit: int | None = None) -> Tuple[int, bytes]:
    """
    Compute chained checksum over the raw bytes of a file up to a limit.

    Parameters
    ----------
    path : Path
        Path to the file.
    limit : int, optional
        Maximum bytes to hash. If None, hash the entire file.

    Returns
    -------
    tuple[int, bytes]
        (bytes_hashed, final_chain_bytes)
    """

    c = ChainedChecksum()
    hashed = 0
    with path.open("rb") as fp:
        if limit is None:
            while True:
                chunk = await asyncio.to_thread(fp.read, CHUNK_SIZE)
                if not chunk:
                    break
                hashed += len(chunk)
                c.next_hash(chunk)
        else:
            remaining = int(limit)
            while remaining > 0:
                to_read = min(remaining, CHUNK_SIZE)
                chunk = await asyncio.to_thread(fp.read, to_read)
                if not chunk:
                    break
                hashed += len(chunk)
                remaining -= len(chunk)
                c.next_hash(chunk)
    return hashed, c.prev_chain


def iter_manifest_entries(paths: List[str]) -> Iterator[Tuple[Path, Path, int]]:
    """
    Yield manifest entries for files in the given paths (files or directories).

    Parameters
    ----------
    paths : List[str]
        List of file or directory paths.

    Yields
    ------
    Tuple[Path, Path, int]
        (absolute_path, relative_path, size)

    Notes
    -----
    - Yields files in sorted order for directories.
    - Skips non-existent or invalid paths.
    """

    if not isinstance(paths, list):
        print("[p2p_copy] send(): files or dirs must be passed as list")
        return
    elif not paths:
        return

    for raw in paths:
        if len(raw) == 1:
            print("[p2p_copy] send(): probably not a file:", raw)
            continue
        p = Path(raw).expanduser()
        if not p.exists():
            print("[p2p_copy] send(): file does not exist:", p)
            continue
        if p.is_file():
            yield p.resolve(), Path(p.name), p.stat().st_size
        else:
            root = p.resolve()
            for sub in sorted(root.rglob("*")):
                if sub.is_file():
                    rel = Path(p.name) / sub.relative_to(root)
                    yield sub.resolve(), rel, sub.stat().st_size


def ensure_dir(p: Path) -> None:
    """
    Ensure the directory exists, creating parents if needed.

    Parameters
    ----------
    p : Path
        The path to ensure is a directory.
    """
    p.mkdir(parents=True, exist_ok=True)
