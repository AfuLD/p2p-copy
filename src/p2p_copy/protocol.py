from dataclasses import dataclass
from typing import Literal, Sequence

PROTOCOL_VERSION: int = 1
ControlKind = Literal["hello", "manifest", "ack", "error", "eof"]

@dataclass(frozen=True)
class Hello:
    code_hash_hex: str
    role: Literal["sender", "receiver"]
    protocol_version: int = PROTOCOL_VERSION

@dataclass(frozen=True)
class ManifestEntry:
    path: str
    size: int
    sha256_hex: str | None = None

@dataclass(frozen=True)
class Manifest:
    entries: Sequence[ManifestEntry]

