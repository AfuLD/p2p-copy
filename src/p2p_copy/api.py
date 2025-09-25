from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, List, Tuple, BinaryIO, Dict

from websockets.asyncio.client import connect

from .compressor import CompressMode, Compressor
from .io_utils import read_in_chunks, iter_manifest_entries, ensure_dir, compute_chain_up_to
from .protocol import (
    Hello, Manifest, ManifestEntry, loads, EOF,
    file_begin, FILE_EOF, pack_chunk, unpack_chunk,
    encrypted_file_begin,
    ReceiverManifest, ReceiverManifestEntry, EncryptedReceiverManifest
)
from .security import ChainedChecksum, SecurityHandler


# ----------------------------- sender --------------------------------

async def send(server: str, code: str, files: List[str],
               encrypt: bool = False,
               compress: CompressMode = CompressMode.auto,
               resume: bool = False) -> int:
    """
    Connects to server and sends files/directories.
    - If 'resume' is True, waits for a receiver manifest and decides skip/append/overwrite existing files.
    - If 'encrypt' is True, encrypts files and file metadata.
    """

    # Closures to break up functions for readability
    async def wait_for_receiver_ready():
        try:
            ready_frame = await asyncio.wait_for(ws.recv(), timeout=300)  # 300s Timeout
            if isinstance(ready_frame, str):
                ready = loads(ready_frame)
                if ready.get("type") != "ready":
                    print("[p2p_copy] send(): unexpected frame after hello"); return 3
            else:
                print("[p2p_copy] send(): expected text frame after hello"); return 3
        except asyncio.TimeoutError:
            print("[p2p_copy] send(): timeout waiting for ready"); return 3


    async def wait_for_receiver_resume_manifest():
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
        except asyncio.TimeoutError:
            print("[p2p_copy] send(): timeout waiting for receiver_manifest"); return 3
        if isinstance(raw, str):
            o = loads(raw)
            t = o.get("type")
            if t == "enc_receiver_manifest" and encrypt:
                try:
                    hidden = bytes.fromhex(o["hidden_manifest"])
                    m_str = secure.decrypt_chunk(hidden).decode()
                    o = loads(m_str)
                    t = o.get("type")
                except Exception:
                    print("[p2p_copy] send():  failed to decrypt encrypted receiver manifest"); return 3

            if t == "receiver_manifest":
                for e in o.get("entries", []):
                    try:
                        p = e["path"]
                        sz = int(e["size"])
                        ch = bytes.fromhex(e["chain_hex"])
                        resume_map[p] = (sz, ch)
                    except Exception:
                        print("[p2p_copy] send():  failed to read receiver manifest"); return 3


    async def pairing_with_receiver():
        await ws.send(hello)
        if receiver_not_ready :=  await wait_for_receiver_ready():
            return receiver_not_ready

        # Send file infos to receiver
        await ws.send(manifest)

        # wait for receiver resume manifest (optionally encrypted)
        if resume and (no_response_manifest := await wait_for_receiver_resume_manifest()):
            return no_response_manifest


    async def determine_file_resume_point():
        hint = resume_map.get(rel_p.as_posix())
        if hint is not None:
            recv_size, recv_chain = hint
            if 0 < recv_size <= size:
                hashed, local_chain = await compute_chain_up_to(abs_p, limit=recv_size)
                if hashed == recv_size and local_chain == recv_chain:
                    return recv_size
                else:
                    # mismatch -> overwrite from scratch
                    return 0
        return 0


    async def send_file():
        append_from = 0
        # Determine resume point (optional)
        if resume and (append_from := await determine_file_resume_point()) == size:
            return # Receiver already has identical file -> skip

        # Open file and optionally seek resume point
        with abs_p.open("rb") as fp:
            if append_from:
                await asyncio.to_thread(fp.seek, append_from, 0)

            # Initialize per-transfer chain and sequence
            chained_checksum = ChainedChecksum()
            seq = 0

            # Determine whether to use compression by compressing the first chunk
            chunk = Compressor.determine_compression(compressor, fp)

            # Build the complete file info header
            file_info = file_begin(rel_p.as_posix(), size, compressor.compression_type, append_from=append_from)

            # Optionally encrypt the file info
            if encrypt:
                enc_file_info = secure.encrypt_chunk(file_info.encode())
                file_info = encrypted_file_begin(enc_file_info)

            # Send file info header
            await ws.send(file_info)

            # Prepare the first frame, first chunk is optionally compressed and then encrypted
            frame: bytes = pack_chunk(seq, chained_checksum.next_hash(chunk), secure.encrypt_chunk(chunk))
            seq += 1

            def next_frame():
                """prepares the next frame of a file to send, optionally compresses and encrypts"""
                compressed_chunk = compressor.compress(chunk)
                enc_chunk = secure.encrypt_chunk(compressed_chunk)
                return pack_chunk(seq, chained_checksum.next_hash(compressed_chunk), enc_chunk)

            # Send remaining chunks
            async for chunk in read_in_chunks(fp):
                # Next frame gets prepared in a parallel thread
                next_frame_coro = asyncio.to_thread(next_frame)
                # Send the current frame while next frame gets prepared
                await ws.send(frame)
                # Complete the next frame
                frame: bytes = await next_frame_coro
                seq += 1

        # Send the last frame
        await ws.send(frame)
        await ws.send(FILE_EOF)


    # Build manifest entries from given file list
    resolved_file_list: List[Tuple[Path, Path, int]] = list(iter_manifest_entries(files))
    if not resolved_file_list:
        print("[p2p_copy] send(): no legal files where passed"); return 3

    entries: List[ManifestEntry] = [ManifestEntry(path=rel.as_posix(), size=size) for (_, rel, size) in resolved_file_list]

    # Initialize security-handler, compressor
    secure = SecurityHandler(code, encrypt)
    compressor = Compressor(mode=compress)

    hello = Hello(type="hello", code_hash_hex=secure.code_hash.hex(), role="sender").to_json()
    manifest = Manifest(type="manifest", resume=resume, entries=entries).to_json()
    if encrypt: # Optionally encrypt the manifest
        manifest = secure.build_encrypted_manifest(manifest)

    # Connect to relay (disable WebSocket internal compression)
    async with connect(server, max_size=None, compression=None) as ws:
        # Stores info returned by the sender about what files are already present
        resume_map: Dict[str, Tuple[int, bytes]] = {}
        # Attempt to connect and optionally exchange info with receiver
        if pairing_failed := await pairing_with_receiver():
            return pairing_failed

        # Transfer each file
        for abs_p, rel_p, size in resolved_file_list:
            await send_file()

        # All done, send message to confirm the end of the copying process
        await ws.send(EOF)
        # Return non-error code
        return 0



# ----------------------------- receiver ------------------------------

async def receive(server: str, code: str,
                  encrypt: bool = False,
                  out: Optional[str] = None) -> int:
    """
    Receives and writes files into 'out' (or current dir).
    If 'resume' is True in the sender's manifest, replies with a receiver manifest
    detailing what is already present (with raw-bytes chained checksum).
    Honors 'append_from' in file headers to append remaining bytes.
    """
    out_dir = Path(out or ".")
    ensure_dir(out_dir)

    # Initialize security-handler
    secure = SecurityHandler(code, encrypt)
    hello = Hello(type="hello", code_hash_hex=secure.code_hash.hex(), role="receiver").to_json()

    # Receiver state
    cur_fp: Optional[BinaryIO] = None
    cur_expected_size: Optional[int] = None
    cur_seq_expected = 0
    bytes_written = 0
    chained_checksum = ChainedChecksum()
    compressor = Compressor()

    # For resume: we may keep a quick map (not strictly needed, but handy for diagnostics)
    resume_known: Dict[str, Tuple[int, bytes]] = {}

    def return_with_error_code():
        if cur_fp is not None:
            cur_fp.close()
        return 4

    async with connect(server, max_size=None, compression=None) as ws:
        await ws.send(hello)

        async for frame in ws:
            # --- binary chunk frames -------------------------------------
            if isinstance(frame, (bytes, bytearray)):
                if cur_fp is None:
                    # Unexpected binary data
                    return return_with_error_code()
                seq, chain, payload = unpack_chunk(frame)
                if seq != cur_seq_expected:
                    print("[p2p_copy] receive(): sequence mismatch", seq, "!=", cur_seq_expected)
                    return return_with_error_code()

                # Decrypt (if enabled) then verify chain over the DECRYPTED (still compressed) chunk
                raw_payload = secure.decrypt_chunk(payload) if encrypt else payload
                if chained_checksum.next_hash(raw_payload) != chain:
                    print("[p2p_copy] receive(): chained checksum mismatch")
                    return return_with_error_code()

                # Decompress (if enabled) to raw bytes, then write
                chunk = compressor.decompress(raw_payload)
                await asyncio.to_thread(cur_fp.write, chunk)

                bytes_written += len(chunk)
                cur_seq_expected += 1
                continue

            # --- text control frames -------------------------------------
            if not isinstance(frame, str):
                print("[p2p_copy] receive(): unknown frame type")
                return return_with_error_code()

            o = loads(frame)
            t = o.get("type")

            # hello from peer can be ignored
            if t == "hello":
                continue

            # encrypted manifest from sender
            if t == "enc_manifest" and encrypt:
                try:
                    # Advance nonce accumulator before decryption if a nonce is provided
                    nonce_hex = o.get("nonce")
                    secure.nonce_hasher.next_hash(bytes.fromhex(nonce_hex))
                    hidden = bytes.fromhex(o["hidden_manifest"])
                    manifest_str = secure.decrypt_chunk(hidden).decode()
                    o = loads(manifest_str)
                    t = o.get("type")
                except Exception as e:
                    print("[p2p_copy] receive(): failed to decrypt manifest", e)
                    return return_with_error_code()

            # plain manifest from sender
            if t == "manifest":
                # gain info on whether to resume
                resume = o.get("resume")

                # Build and send our receiver manifest (possibly encrypted)
                entries = o.get("entries", []) or []
                reply_entries: List[ReceiverManifestEntry] = []

                for e in entries:
                    try:
                        rel = Path(e["path"])
                        sender_size = int(e["size"])  # noqa: F841  (kept for clarity / future checks)
                    except Exception:
                        continue

                    local_path = (out_dir / rel).resolve()
                    if local_path.is_file():
                        local_size = local_path.stat().st_size
                        if local_size > 0:
                            hashed, chain_b = await compute_chain_up_to(local_path)
                            resume_known[rel.as_posix()] = (hashed, chain_b)
                            reply_entries.append(
                                ReceiverManifestEntry(
                                    path=rel.as_posix(),
                                    size=hashed,
                                    chain_hex=chain_b.hex(),
                                )
                            )

                # Send resume manifest back only if expected
                if resume and encrypt:
                    # Serialize cleartext receiver manifest then encrypt
                    clear = ReceiverManifest(type="receiver_manifest", entries=reply_entries).to_json().encode()
                    hidden = secure.encrypt_chunk(clear)
                    reply = EncryptedReceiverManifest(
                        type="enc_receiver_manifest",
                        hidden_manifest=hidden.hex()
                    ).to_json()
                    await ws.send(reply)
                elif resume:
                    await ws.send(ReceiverManifest(type="receiver_manifest", entries=reply_entries).to_json())
                continue

            # file header (possibly encrypted)
            if t == "enc_file" and encrypt:
                try:
                    hidden = bytes.fromhex(o["hidden_file"])
                    file_str = secure.decrypt_chunk(hidden).decode()
                    o = loads(file_str)
                    t = o.get("type")
                except Exception as e:
                    print("[p2p_copy] receive(): failed to decrypt file info", e)
                    return return_with_error_code()

            if t == "file":
                # Close any previous file just in case
                if cur_fp is not None:
                    print("[p2p_copy] receive(): got new file while previous still open")
                    return return_with_error_code()

                try:
                    rel_path = o["path"]
                    total_size: int = o.get("size")
                    compression = o.get("compression", "none")
                    append_from: int = o.get("append_from")
                except Exception:
                    print("[p2p_copy] receive(): bad file header", o)
                    return return_with_error_code()

                dest = (out_dir / Path(rel_path)).resolve()
                ensure_dir(dest.parent)

                open_mode = "wb"
                expected_remaining = total_size
                if append_from > 0 and dest.exists() and dest.is_file():
                    local_size = dest.stat().st_size
                    if 0 <= append_from <= total_size and local_size == append_from:
                        open_mode = "ab"
                        expected_remaining = total_size - append_from
                    else:
                        # size mismatch -> overwrite from scratch
                        expected_remaining = total_size

                # noinspection PyTypeChecker
                cur_fp = dest.open(open_mode)
                cur_expected_size = expected_remaining
                cur_seq_expected = 0
                bytes_written = 0
                compressor.set_decompression(compression)
                chained_checksum = ChainedChecksum()
                continue

            if t == "file_eof":
                if cur_fp is None:
                    print("[p2p_copy] receive(): got file_eof without open file")
                    return return_with_error_code()
                # Validate expected size
                elif cur_expected_size is not None and bytes_written != cur_expected_size:
                    print("[p2p_copy] receive(): size mismatch", bytes_written, "!=", cur_expected_size)
                    return return_with_error_code()
                else:
                    cur_fp.close()
                    cur_fp = None
                continue

            if t == "eof":
                break

            # Exit on unknown text control
            print("[p2p_copy] receive(): unexpected control", o)
            return return_with_error_code()

    # ensure no file left open
    if cur_fp is not None:
        print("[p2p_copy] receive(): stream ended while file open")
        return return_with_error_code()
    return 0
