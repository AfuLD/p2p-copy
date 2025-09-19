from __future__ import annotations

import asyncio
import collections
from pathlib import Path
from typing import Iterable, Iterator, Tuple, BinaryIO

CHUNK_SIZE = 1 << 20  # 1 MiB

async def read_in_chunks(fp: BinaryIO, *, chunk_size: int = CHUNK_SIZE) -> collections.AsyncIterable[bytes]:
    """reads in bytes from a file in chunks, starts at current file position"""
    while True:
        # Read from disk without blocking the event-loop
        chunk = await asyncio.to_thread(fp.read,chunk_size)
        if not chunk:
            break
        yield chunk

def iter_manifest_entries(paths: Iterable[str]) -> Iterator[Tuple[Path, Path, int]]:
    """Yields tuples of (absolute path, relative path, size) for files in the given paths.

    Parameters
    ----------
    paths : Iterable[str]
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
    - Non-existent paths are silently skipped.
    - Symlinks are resolved to their target paths.
    - Tilde (~) is expanded to the user's home directory.
    - May raise FileNotFoundError or PermissionError if file access fails.
    """
    for raw in paths:
        p = Path(raw).expanduser()
        if not p.exists():
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
