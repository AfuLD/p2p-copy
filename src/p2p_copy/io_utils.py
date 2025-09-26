from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterator, Tuple, BinaryIO, List, AsyncIterable

from p2p_copy.security import ChainedChecksum

CHUNK_SIZE = 1 << 20  # 1 MiB

async def read_in_chunks(fp: BinaryIO, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterable[bytes]:
    """reads in bytes from a file in chunks, starts at current file position"""
    while True:
        # Read from disk without blocking the event-loop
        chunk = await asyncio.to_thread(fp.read,chunk_size)
        if not chunk:
            break
        yield chunk

async def compute_chain_up_to(path: Path, limit: int | None = None) -> Tuple[int, bytes]:
    """
    Compute chained checksum over the RAW BYTES on disk for 'path'.
    If limit is given, only the first 'limit' bytes are included.
    Returns (bytes_hashed, final_chain_bytes).
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
    """Yields tuples of (absolute path, relative path, size) for files in the given paths.

    Parameters
    ----------
    paths : List[str]
        An iterable of strings representing file or directory paths.

    Yields
    ------
    Tuple[Path, Path, int]
        A tuple containing:
        - Absolute path (Path): The resolved absolute path of the file.
        - Relative path (Path): The path relative to the input path's basename
          (e.g., for input `/foo/mydir`, files yield `mydir/subpath`).
        - Size (int): The file size in bytes.

    Examples
    --------
    For a single file:
    >>> list(iter_manifest_entries(["/foo/bar.txt"]))
    [(Path("/foo/bar.txt"), Path("bar.txt"), 1234)]

    For a directory:
    >>> list(iter_manifest_entries(["/foo/mydir"]))
    [(Path("/foo/mydir/file1.txt"), Path("mydir/file1.txt"), 100),
     (Path("/foo/mydir/subdir/file2.txt"), Path("mydir/subdir/file2.txt"), 200)]

    Notes
    -----
    - Files in directories are yielded in sorted order (alphabetically by path).
    - Non-existent paths are reported.
    - Symlinks are resolved to their target paths.
    - Tilde (~) is expanded to the user's home directory.
    - May raise FileNotFoundError or PermissionError if file access fails.
    """

    if not isinstance(paths, list):
        print("[p2p_copy] send(): files or dirs must be passed as list"); return
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
    p.mkdir(parents=True, exist_ok=True)
