from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal, Sequence, Any, Dict, Tuple
import json, struct

PROTOCOL_VERSION: int = 5

# --- helpers ---------------------------------------------------------

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

@dataclass(frozen=True)
class Manifest:
    type: Literal["manifest"]
    entries: Sequence[ManifestEntry]
    resume: bool = False
    def to_json(self) -> str:
        return dumps({
            "type": "manifest",
            "resume": self.resume,
            "entries": [asdict(e) for e in self.entries]
        })

@dataclass(frozen=True)
class EncryptedManifest:
    type: Literal["enc_manifest"]
    nonce: str
    hidden_manifest: str
    def to_json(self) -> str:
        return dumps({
            "type": "enc_manifest",
            "nonce": self.nonce,
            "hidden_manifest": self.hidden_manifest
        })

# --- NEW: receiver resume manifest ----------------------------------

@dataclass(frozen=True)
class ReceiverManifestEntry:
    """
    The receiver reports what it already has for a given path:
    - size: bytes present on disk
    - chain_hex: chained checksum over the RAW BYTES up to 'size'
    """
    path: str
    size: int
    chain_hex: str

@dataclass(frozen=True)
class ReceiverManifest:
    type: Literal["receiver_manifest"]
    entries: Sequence[ReceiverManifestEntry]
    def to_json(self) -> str:
        return dumps({
            "type": "receiver_manifest",
            "entries": [asdict(e) for e in self.entries]
        })

@dataclass(frozen=True)
class EncryptedReceiverManifest:
    type: Literal["enc_receiver_manifest"]
    hidden_manifest: str
    def to_json(self) -> str:
        return dumps({
            "type": "enc_receiver_manifest",
            "hidden_manifest": self.hidden_manifest
        })

# --- file control ----------------------------------------------------

def file_begin(path: str, size: int, compression: str = "none", append_from: int = 0) -> str:
    """
    Start of a file stream. If append_from is given, it indicates the sender will
    only send bytes from [append_from .. size) and the receiver should open in 'ab'.
    """
    msg: Dict[str, Any] = {
        "type": "file",
        "path": path,
        "size": int(size),
        "compression": compression,
        "append_from": append_from
    }

    return dumps(msg)

def encrypted_file_begin(hidden_file_info: bytes) -> str:
    """
    Wrap a file header into an encrypted control frame.
    """
    payload = {
        "type": "enc_file",
        "hidden_file": hidden_file_info.hex()
    }
    return dumps(payload)

READY = dumps({"type": "ready"})

FILE_EOF = dumps({"type":"file_eof"})

EOF = dumps({"type":"eof"})

# --- chunked framing -------------------------------------------------

# Binary frames: [ seq: uint64_be | chain: 32 bytes | payload... ]
# The 'chain' is sha256(prev_chain || payload)
CHUNK_HEADER = struct.Struct("!Q32s")

def pack_chunk(seq: int, chain: bytes, payload: bytes) -> bytes:
    return CHUNK_HEADER.pack(seq, chain) + payload

def unpack_chunk(frame: bytes) -> Tuple[int, bytes, bytes]:
    if len(frame) < CHUNK_HEADER.size:
        raise ValueError("short chunk frame")
    seq, chain = CHUNK_HEADER.unpack(frame[:CHUNK_HEADER.size])
    payload = frame[CHUNK_HEADER.size:]
    return seq, chain, payload
