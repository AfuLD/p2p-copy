from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal, Sequence, Any, Dict, Tuple
import json, hashlib, struct

from p2p_copy.checksum import ChainedChecksum

PROTOCOL_VERSION: int = 1

# --- helpers ---------------------------------------------------------

def code_to_hash_hex(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()

def dumps(msg: Dict[str, Any]) -> str:
    return json.dumps(msg, separators=(",", ":"), ensure_ascii=False)

def loads(s: str) -> Dict[str, Any]:
    return json.loads(s)

# --- control messages ------------------------------------------------

@dataclass(frozen=True)
class Hello:
    type: Literal["hello"]
    code_hash_hex: str
    role: Literal["sender","receiver"]
    def to_json(self) -> str:
        return dumps({"type":"hello","code_hash_hex":self.code_hash_hex,"role":self.role})

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
        return dumps({"type":"manifest","entries":[asdict(e) for e in self.entries]})

def file_begin(path: str, size: int, compression: str = "none") -> str:
    return dumps({"type":"file","path":path,"size":size,"compression":compression})

FILE_EOF = dumps({"type":"file_eof"})

EOF = dumps({"type":"eof"})

# --- chunked framing -------------------------------------------------

# Binary frames: [ seq: uint64_be | chain: 32 bytes | payload... ]
# The 'chain' is sha256(prev_chain || payload)
CHUNK_HEADER = struct.Struct("!Q32s")

def pack_chunk(seq: int, chained_checksum: ChainedChecksum, payload: bytes) -> bytes:
    chain = chained_checksum.next_hash(payload)
    return CHUNK_HEADER.pack(seq, chain) + payload

def unpack_chunk(frame: bytes) -> Tuple[int, bytes, bytes]:
    if len(frame) < CHUNK_HEADER.size:
        raise ValueError("short chunk frame")
    seq, chain = CHUNK_HEADER.unpack(frame[:CHUNK_HEADER.size])
    payload = frame[CHUNK_HEADER.size:]
    return seq, chain, payload