from pathlib import Path
from typing import Iterable, Iterator

def iter_files(paths: Iterable[str]) -> Iterator[Path]:
    for p in paths:
        yield Path(p)

def ensure_dir(p: Path) -> None:
    """Create directory p (and parents) if it doesn't exist."""
    p.mkdir(parents=True, exist_ok=True)