from pathlib import Path
from typing import Iterable, Iterator

def iter_files(paths: Iterable[str]) -> Iterator[Path]:
    for p in paths:
        yield Path(p)
