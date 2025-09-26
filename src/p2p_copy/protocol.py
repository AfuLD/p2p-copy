from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal, Sequence, Any, Dict, Tuple
import json, struct


# --- helpers ---------------------------------------------------------

def dumps(msg: Dict[str, Any]) -> str:
    """
    JSON-dump a message with compact separators.

    Parameters
    ----------
    msg : Dict[str, Any]
        The message to serialize.

    Returns
    -------
    str
        Compact JSON string.
    """
    return json.dumps(msg, separators=(",", ":"), ensure_ascii=False)


def loads(s: str) -> Dict[str, Any]:
    """
    JSON-load a string into a dict.

    Parameters
    ----------
    s : str
        JSON string.

    Returns
    -------
    Dict[str, Any]
        Parsed dictionary.
    """
    return json.loads(s)


# --- control messages ------------------------------------------------

@dataclass(frozen=True)
class Hello:
    """
    Hello message for connection initiation.

    Parameters
    ----------
    type : Literal["hello"]
        Message type.
    code_hash_hex : str
        Hex-encoded hash of the shared code.
    role : Literal["sender", "receiver"]
        The role of this client.
    """
    type: Literal["hello"]
    code_hash_hex: str
    role: Literal["sender", "receiver"]

    def to_json(self) -> str:
        return dumps({"type": "hello", "code_hash_hex": self.code_hash_hex, "role": self.role})


@dataclass(frozen=True)
class ManifestEntry:
    """
    Entry in a file manifest.

    Parameters
    ----------
    path : str
        Relative path of the file.
    size : int
        File size in bytes.
    """
    path: str
    size: int


@dataclass(frozen=True)
class Manifest:
    """
    Manifest of files to send.

    Parameters
    ----------
    type : Literal["manifest"]
        Message type.
    entries : Sequence[ManifestEntry]
        List of file entries.
    resume : bool, optional
        Whether to enable resume. Default is False.
    """
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
    """
    Encrypted manifest for secure transmission.

    Parameters
    ----------
    type : Literal["enc_manifest"]
        Message type.
    nonce : str
        Hex-encoded nonce that is used as random seed.
        Further nonces are based on this and used for encryption.
        Must be shared with receiver so it can decrypt accordingly.
    hidden_manifest : str
        Hex-encoded encrypted manifest.
    """
    type: Literal["enc_manifest"]
    nonce: str
    hidden_manifest: str

    def to_json(self) -> str:
        return dumps({
            "type": "enc_manifest",
            "nonce": self.nonce,
            "hidden_manifest": self.hidden_manifest
        })


@dataclass(frozen=True)
class ReceiverManifestEntry:
    """
    Receiver's report of existing file state for resume.

    Parameters
    ----------
    path : str
        Relative path.
    size : int
        Bytes already present.
    chain_hex : str
        Hex-encoded chained checksum up to 'size'.
    """
    path: str
    size: int
    chain_hex: str


@dataclass(frozen=True)
class ReceiverManifest:
    """
    Manifest from receiver reporting existing files.

    Parameters
    ----------
    type : Literal["receiver_manifest"]
        Message type.
    entries : Sequence[ReceiverManifestEntry]
        List of entries.
    """
    type: Literal["receiver_manifest"]
    entries: Sequence[ReceiverManifestEntry]

    def to_json(self) -> str:
        return dumps({
            "type": "receiver_manifest",
            "entries": [asdict(e) for e in self.entries]
        })


@dataclass(frozen=True)
class EncryptedReceiverManifest:
    """
    Encrypted receiver manifest.

    Parameters
    ----------
    type : Literal["enc_receiver_manifest"]
        Message type.
    hidden_manifest : str
        Hex-encoded encrypted manifest.
    """
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
    Create a file begin control message.

    Parameters
    ----------
    path : str
        Relative path.
    size : int
        Total file size.
    compression : str, optional
        Compression type. Default is 'none'.
    append_from : int, optional
        Byte offset to append from. Default is 0.

    Returns
    -------
    str
        JSON string of the message.
    """
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
    Wrap encrypted file info in a control message.

    Parameters
    ----------
    hidden_file_info : bytes
        Encrypted file begin data.

    Returns
    -------
    str
        JSON string of the enc_file message.
    """
    payload = {
        "type": "enc_file",
        "hidden_file": hidden_file_info.hex()
    }
    return dumps(payload)


READY = dumps({"type": "ready"})

FILE_EOF = dumps({"type": "file_eof"})

EOF = dumps({"type": "eof"})

# --- chunked framing -------------------------------------------------

# Binary frames: [ seq: uint64_be | chain: 32 bytes | payload... ]
# The 'chain' is sha256(prev_chain || payload)
CHUNK_HEADER = struct.Struct("!Q32s")


def pack_chunk(seq: int, chain: bytes, payload: bytes) -> bytes:
    """
    Pack a chunk into a binary frame.

    Parameters
    ----------
    seq : int
        Sequence number.
    chain : bytes
        32-byte chain checksum.
    payload : bytes
        The data payload.

    Returns
    -------
    bytes
        Packed frame.
    """
    return CHUNK_HEADER.pack(seq, chain) + payload


def unpack_chunk(frame: bytes) -> Tuple[int, bytes, bytes]:
    """
    Unpack a binary chunk frame.

    Parameters
    ----------
    frame : bytes
        The binary frame.

    Returns
    -------
    Tuple[int, bytes, bytes]
        (seq, chain, payload)

    Raises
    ------
    ValueError
        If frame is too short.
    """
    if len(frame) < CHUNK_HEADER.size:
        raise ValueError("short chunk frame")
    seq, chain = CHUNK_HEADER.unpack(frame[:CHUNK_HEADER.size])
    payload = frame[CHUNK_HEADER.size:]
    return seq, chain, payload
