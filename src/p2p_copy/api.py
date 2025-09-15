from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, List, Tuple, BinaryIO

from websockets.asyncio.client import connect

from p2p_copy.compressor import CompressMode  # reserved for later phases
from .checksum import ChainedChecksum
from .chunker import read_in_chunks, CHUNK_SIZE
from .io_utils import iter_manifest_entries, ensure_dir
from .protocol import (
    Hello, Manifest, ManifestEntry, code_to_hash_hex, loads, EOF,
    file_begin, FILE_EOF, pack_chunk, unpack_chunk
)


# ----------------------------- sender --------------------------------

async def send(server: str, code: str, files: Iterable[str],
        encrypt: bool = False,                       # reserved (phase 4+)
        compress: CompressMode = CompressMode.auto,  # reserved (phase 4)
        resume: bool = True,                         # reserved (phase 5)
) -> int:
    # Build manifest
    entries: List[ManifestEntry] = []
    resolved: List[Tuple[Path, Path, int]] = list(iter_manifest_entries(files))
    if not resolved:
        print("[p2p_copy] send(): no files provided"); return 2
    for abs_p, rel_p, size in resolved:
        entries.append(ManifestEntry(path=rel_p.as_posix(), size=size))

    hello = Hello(type="hello", code_hash_hex=code_to_hash_hex(code), role="sender").to_json()
    manifest = Manifest(type="manifest", entries=entries).to_json()

    async with connect(server, max_size=None) as ws:
        # hello + manifest
        await ws.send(hello)
        await ws.send(manifest)

        # send files
        for abs_p, rel_p, size in resolved:
            await ws.send(file_begin(rel_p.as_posix(), size))
            chained_checksum = ChainedChecksum()
            seq = 0

            with abs_p.open("rb") as fp:
                for chunk in read_in_chunks(fp, chunk_size=CHUNK_SIZE):
                    frame: bytes = pack_chunk(seq, chained_checksum, chunk)
                    await ws.send(frame)
                    seq += 1

            await ws.send(FILE_EOF)

        await ws.send(EOF)
    return 0

# ----------------------------- receiver -------------------------------

async def receive(server: str, code: str,
        resume: bool = True,  # reserved
        out: Optional[str] = None,
) -> int:
    out_dir = Path(out or ".")
    ensure_dir(out_dir)

    hello = Hello(type="hello", code_hash_hex=code_to_hash_hex(code), role="receiver").to_json()

    # Receiver state
    cur_fp: Optional[BinaryIO] = None
    cur_path: Optional[Path] = None
    cur_expected_size: Optional[int] = None
    cur_seq_expected = 0
    chained_checksum = ChainedChecksum()
    bytes_written = 0

    def close_current():
        nonlocal cur_fp, cur_path
        if cur_fp:
            cur_fp.close()
        cur_fp = None
        cur_path = None

    async with connect(server, max_size=None) as ws:
        await ws.send(hello)
        # Process stream
        async for frame in ws:
            if isinstance(frame, bytes):
                if cur_fp is None:
                    print("[p2p_copy] receive(): unexpected binary frame (no file announced)"); return 4
                try:
                    seq, chain, payload = unpack_chunk(frame)
                except Exception as e:
                    print("[p2p_copy] receive(): bad chunk frame:", e); return 4
                if seq != cur_seq_expected:
                    print(f"[p2p_copy] receive(): bad chunk sequence: got {seq}, expected {cur_seq_expected}"); return 4

                # verify chain
                expected_chain = chained_checksum.next_hash(payload)
                if chain != expected_chain:
                    print("[p2p_copy] receive(): chain checksum mismatch"); return 4
                # write
                cur_fp.write(payload)
                bytes_written += len(payload)
                cur_seq_expected += 1
                continue

            # Text frame
            try:
                o = loads(frame)
            except Exception:
                print("[p2p_copy] receive(): unexpected text frame", frame); return 4
            t = o.get("type")

            if t == "manifest":
                # optional: pre-create directories
                for e in o.get("entries", []):
                    rel = Path(e.get("path",""))
                    if rel.parent:
                        ensure_dir(out_dir / rel.parent)
                continue

            if t == "file":
                # start new file
                if cur_fp is not None:
                    print("[p2p_copy] receive(): got new file while previous still open"); return 4
                rel = Path(o.get("path",""))
                size = int(o.get("size",0))
                dest = out_dir / rel
                ensure_dir(dest.parent)
                cur_fp = dest.open("wb")
                cur_path = dest
                cur_expected_size = size
                cur_seq_expected = 0
                chained_checksum = ChainedChecksum()
                bytes_written = 0
                continue

            if t == "file_eof":
                if cur_fp is None:
                    print("[p2p_copy] receive(): file_eof without open file"); return 4
                cur_fp.flush()
                close_current()
                if cur_expected_size is not None and bytes_written != cur_expected_size:
                    print("[p2p_copy] receive(): size mismatch"); return 4
                continue

            if t == "eof":
                break

            if t == "hello":
                # peer hello can be ignored by clients
                continue

            print("[p2p_copy] receive(): unexpected control", o); return 4

    # ensure no file left open
    if cur_fp is not None:
        print("[p2p_copy] receive(): stream ended while file open"); return 4
    return 0
