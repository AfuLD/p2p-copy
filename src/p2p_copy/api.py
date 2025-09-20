from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Iterable, Optional, List, Tuple, BinaryIO

from websockets.asyncio.client import connect

from .compressor import CompressMode, Compressor
from .security import ChainedChecksum, SecurityHandler
from .io_utils import read_in_chunks, iter_manifest_entries, ensure_dir
from .protocol import (
    Hello, Manifest, ManifestEntry, loads, EOF,
    file_begin, FILE_EOF, pack_chunk, unpack_chunk, EncryptedManifest, encrypted_file_begin
)

# ----------------------------- sender --------------------------------

async def send(server: str, code: str, files: Iterable[str],
               encrypt: bool = False,                       # reserved (phase 4+)
               compress: CompressMode = CompressMode.auto,
               resume: bool = True,                         # reserved (phase 5)
               ) -> int:
    # Build manifest
    entries: List[ManifestEntry] = []
    resolved: List[Tuple[Path, Path, int]] = list(iter_manifest_entries(files))
    if not resolved:
        print("[p2p_copy] send(): no files provided"); return 2
    for abs_p, rel_p, size in resolved:
        entries.append(ManifestEntry(path=rel_p.as_posix(), size=size))

    # Initialize security-handler
    start_nonce = os.urandom(32)
    secure = SecurityHandler(code, encrypt, start_nonce)

    hello = Hello(type="hello", code_hash_hex=secure.code_hash.hex(), role="sender").to_json()
    manifest = Manifest(type="manifest", entries=entries).to_json()
    if encrypt:
        enc_manifest = secure.encrypt_chunk(manifest.encode())
        manifest = EncryptedManifest(type="enc_manifest", nonce=start_nonce.hex(), hidden_manifest=enc_manifest.hex()).to_json()

    async with connect(server, max_size=None, compression=None) as ws:  # Disable WebSocket compression
        # hello + manifest
        await ws.send(hello)
        await ws.send(manifest)

        # Initialize compressor
        compressor = Compressor(compress)

        # Send files
        for abs_p, rel_p, size in resolved:
            with abs_p.open("rb") as fp:
                chained_checksum = ChainedChecksum()
                seq = 0

                # Determine compression mode for this file and get first chunk
                chunk = compressor.determine_compression(fp)

                file_info = file_begin(rel_p.as_posix(), size, compressor.compression_type)
                if encrypt:
                    enc_file_info = secure.encrypt_chunk(file_info.encode())
                    file_info = encrypted_file_begin(enc_file_info)

                # Send file_begin with compression mode info for receiver
                last_send = ws.send(file_info)

                # Encrypt (if selected)
                enc_chunk = secure.encrypt_chunk(chunk)

                # send the first prepared chunk
                frame: bytes = pack_chunk(seq, chained_checksum.next_hash(chunk), enc_chunk)
                await last_send
                last_send = ws.send(frame)
                seq += 1

                # send remaining chunks
                async for _chunk in read_in_chunks(fp):
                    chunk = compressor.compress(_chunk)
                    enc_chunk = secure.encrypt_chunk(chunk)

                    frame: bytes = pack_chunk(seq, chained_checksum.next_hash(chunk), enc_chunk)
                    await last_send
                    last_send = ws.send(frame)
                    seq += 1

            await last_send
            await ws.send(FILE_EOF)

        await ws.send(EOF)
    return 0

# ----------------------------- receiver -------------------------------

async def receive(server: str, code: str,
                  encrypt: bool = False,
                  out: Optional[str] = None,
                  ) -> int:
    out_dir = Path(out or ".")
    ensure_dir(out_dir)

    # Initialize security-handler
    secure = SecurityHandler(code, encrypt)
    hello = Hello(type="hello", code_hash_hex=secure.code_hash.hex(), role="receiver").to_json()

    # Receiver state
    cur_fp: Optional[BinaryIO] = None
    cur_path: Optional[Path] = None
    cur_expected_size: Optional[int] = None
    cur_seq_expected = 0
    chained_checksum = ChainedChecksum()
    bytes_written = 0
    compressor = Compressor(CompressMode.off)  # Initialize with off, set per file

    def close_current():
        nonlocal cur_fp, cur_path
        if cur_fp:
            cur_fp.close()
        cur_fp = None
        cur_path = None
        compressor.set_decompression("none")  # Reset decompression

    async with connect(server, max_size=None, compression=None) as ws:  # Disable WebSocket compression
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

                payload = secure.decrypt_chunk(payload)

                # verify chain
                expected_chain = chained_checksum.next_hash(payload)
                if chain != expected_chain:
                    print("[p2p_copy] receive(): chain checksum mismatch"); return 4

                # Decompress if necessary
                payload = compressor.decompress(payload)

                # Write to disk without blocking the event-loop
                await asyncio.to_thread(cur_fp.write, payload)
                bytes_written += len(payload)
                cur_seq_expected += 1
                continue

            # Text frame
            try:
                o = loads(frame)
            except:
                print("[p2p_copy] receive(): unexpected text frame", frame); return 4
            t = o.get("type")

            if t == "enc_manifest":
                try:
                    manifest_str = ""
                    # Load nonce to decrypt
                    secure.nonce_hasher.next_hash(bytes.fromhex(o.get("nonce")))
                    hidden_manifest = o.get("hidden_manifest")
                    manifest_str = secure.decrypt_chunk(bytes.fromhex(hidden_manifest)).decode()

                    # Continue with decrypted manifest
                    o = loads(manifest_str)
                    t = o.get("type")
                except:
                    print("[p2p_copy] receive(): failed to decrypt manifest", o,
                          "\ndecrypted:", manifest_str); return 4

            if t == "manifest":
                # optional: pre-create directories
                for e in o.get("entries", []):
                    rel = Path(e.get("path",""))
                    if rel.parent:
                        ensure_dir(out_dir / rel.parent)
                continue

            if t == "enc_file":
                # decrypt file info
                try:
                    file_str = ""
                    hidden_file = o.get("hidden_file")
                    file_str = secure.decrypt_chunk(bytes.fromhex(hidden_file)).decode()

                    # Continue with decrypted file info
                    o = loads(file_str)
                    t = o.get("type")
                except:
                    print("[p2p_copy] receive(): failed to decrypt file info", o,
                          "\ndecrypted:", file_str); return 4


            if t == "file":
                # start new file
                if cur_fp is not None:
                    print("[p2p_copy] receive(): got new file while previous still open"); return 4
                rel = Path(o.get("path",""))
                size = int(o.get("size",0))
                compression = o.get("compression", "none")  # Read compression mode
                dest = out_dir / rel
                ensure_dir(dest.parent)
                cur_fp = dest.open("wb")
                cur_path = dest
                cur_expected_size = size
                cur_seq_expected = 0
                compressor.set_decompression(compression)
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
        close_current()
        print("[p2p_copy] receive(): stream ended while file open"); return 4
    return 0