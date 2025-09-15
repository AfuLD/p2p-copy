from __future__ import annotations
from pathlib import Path
from typing import Iterable, Iterator, Tuple

def iter_manifest_entries(paths: Iterable[str]) -> Iterator[Tuple[Path, Path, int]]:
    """
    Expand a list of input paths (files or directories) into a stream of
    (abs_path, rel_path, size) tuples. The rel_path keeps the provided top-level
    name (basename of the argument), so sending `/foo/bar` will produce
    `bar/...` on the receiver.
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
