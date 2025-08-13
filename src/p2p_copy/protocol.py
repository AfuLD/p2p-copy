from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal, Sequence, Any, Dict
import json, hashlib

PROTOCOL_VERSION: int = 1

def code_to_hash_hex(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()

def dumps(msg: Dict[str, Any]) -> str:
    return json.dumps(msg, separators=(",", ":"), ensure_ascii=False)

def loads(s: str) -> Dict[str, Any]:
    return json.loads(s)

@dataclass(frozen=True)
class Hello:
    type: Literal["hello"]
    code_hash_hex: str
    role: Literal["sender", "receiver"]
    protocol_version: int = PROTOCOL_VERSION
    def to_json(self) -> str: return dumps(asdict(self))

@dataclass(frozen=True)
class ManifestEntry:
    path: str
    size: int
    sha256_hex: str | None = None

@dataclass(frozen=True)
class Manifest:
    type: Literal["manifest"]
    entries: Sequence[ManifestEntry]
    def to_json(self) -> str:
        return dumps({"type": "manifest", "entries": [asdict(e) for e in self.entries]})

EOF = dumps({"type": "eof"})
