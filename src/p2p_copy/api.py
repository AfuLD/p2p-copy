from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, List, Tuple, BinaryIO, Dict

from websockets.asyncio.client import connect

from .compressor import CompressMode, Compressor
from .io_utils import read_in_chunks, iter_manifest_entries, ensure_dir, compute_chain_up_to, CHUNK_SIZE
from .protocol import (
    Hello, Manifest, ManifestEntry, loads, EOF,
    file_begin, FILE_EOF, pack_chunk, unpack_chunk,
    encrypted_file_begin,
    ReceiverManifest, ReceiverManifestEntry, EncryptedReceiverManifest
)
from .security import ChainedChecksum, SecurityHandler


# ----------------------------- sender --------------------------------

async def send(server: str, code: str, files: List[str],
               *, encrypt: bool = False,
               compress: CompressMode = CompressMode.auto,
               resume: bool = False) -> int:
    """
    Send one or more files or directories to a paired receiver via the relay server.

    This command connects to the specified WebSocket relay server, authenticates using
    the shared passphrase (hashed for pairing), and streams the provided files/directories
    in chunks to the receiver. Supports directories by recursively including all files
    in alphabetical order. Optional end-to-end encryption (AES-GCM) and compression
    (Zstandard, auto-detected per file) can be enabled. If resume is enabled, it
    coordinates with the receiver to skip complete files or append to partial ones
    based on chained checksum verification.

    Parameters
    ----------
    server : str
        The WebSocket server URL (ws:// or wss://).
    code : str
        The shared passphrase/code for pairing.
    files : List[str]
        List of files and/or directories to send.
    encrypt : bool, optional
        Enable end-to-end encryption. Default is False.
        Receiver needs to use the same setting.
    compress : CompressMode, optional
        Compression mode. Default is 'auto'.
    resume : bool, optional
        Enable resume of partial transfers. Default is False.
        If True, attempt to skip identical files and append
        incomplete files based on receiver feedback.

    Returns
    -------
    int
        Exit code: 0 on success, non-zero on error.

    Notes
    -----
    - Supports resuming by comparing checksums of partial files.
    - Uses chunked streaming for large files.
    """

    # Closures to break up functions for readability

    async def wait_for_receiver_ready():
        try:
            ready_frame = await asyncio.wait_for(ws.recv(), timeout=300)  # 300s Timeout
            if isinstance(ready_frame, str):
                ready = loads(ready_frame)
                if ready.get("type") != "ready":
                    print("[p2p_copy] send(): unexpected frame after hello")
                    return 3
            else:
                print("[p2p_copy] send(): expected text frame after hello")
                return 3
        except asyncio.TimeoutError:
            print("[p2p_copy] send(): timeout waiting for ready")
            return 3

    async def wait_for_receiver_resume_manifest():
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
        except asyncio.TimeoutError:
            print("[p2p_copy] send(): timeout waiting for receiver_manifest")
            return 3
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
                    print("[p2p_copy] send():  failed to decrypt encrypted receiver manifest")
                    return 3

            if t == "receiver_manifest":
                for e in o.get("entries", []):
                    try:
                        p = e["path"]
                        sz = int(e["size"])
                        ch = bytes.fromhex(e["chain_hex"])
                        resume_map[p] = (sz, ch)
                    except Exception:
                        print("[p2p_copy] send():  failed to read receiver manifest")
                        return 3

    async def pairing_with_receiver():
        await ws.send(hello)
        if receiver_not_ready := await wait_for_receiver_ready():
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
            return  # Receiver already has identical file -> skip

        # Open file and optionally seek resume point
        with abs_p.open("rb") as fp:
            if append_from:
                await asyncio.to_thread(fp.seek, append_from, 0)

            # Initialize per-transfer chain and sequence
            chained_checksum = ChainedChecksum()
            seq = 0

            # Determine whether to use compression by compressing the first chunk
            chunk = await asyncio.to_thread(fp.read, CHUNK_SIZE)
            chunk = await Compressor.determine_compression(compressor, chunk)

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

    # End of Closures

    # Build manifest entries from given file list
    resolved_file_list: List[Tuple[Path, Path, int]] = list(iter_manifest_entries(files))
    if not resolved_file_list:
        print("[p2p_copy] send(): no legal files where passed")
        return 3

    entries: List[ManifestEntry] = [ManifestEntry(path=rel.as_posix(), size=size) for (_, rel, size) in
                                    resolved_file_list]

    # Initialize security-handler, compressor
    secure = SecurityHandler(code, encrypt)
    compressor = Compressor(mode=compress)

    hello = Hello(type="hello", code_hash_hex=secure.code_hash.hex(), role="sender").to_json()
    manifest = Manifest(type="manifest", resume=resume, entries=entries).to_json()
    if encrypt:  # Optionally encrypt the manifest
        manifest = secure.build_encrypted_manifest(manifest)

    # Connect to relay (disable WebSocket internal compression)
    async with connect(server, max_size=2**21, compression=None) as ws:
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
                  *, encrypt: bool = False,
                  out: Optional[str] = None) -> int:
    """
    Receive files from a paired sender via the relay server and write to the output directory.

    This command connects to the relay server, pairs using the shared passphrase hash,
    and receives a manifest of incoming files/directories. Files are written to the
    output directory, preserving relative paths from the manifest. Supports optional
    end-to-end decryption (matching sender's encryption) and decompression. If the
    sender requests resume, this receiver reports existing file states (via checksums)
    to enable skipping or appending.

    Parameters
    ----------
    server : str
        The WebSocket server URL (ws:// or wss://).
    code : str
        The shared passphrase/code for pairing.
    encrypt : bool, optional
        Enable end-to-end encryption. Default is False.
        Sender needs to use the same setting.
    out : str, optional
        Output directory. Default is current directory.

    Returns
    -------
    int
        Exit code: 0 on success, non-zero on error.

    Notes
    -----
    - Supports resume if sender requests it.
    - Writes files to the output directory, preserving relative paths.
    - Info on whether to resume and compress is received from the sender
    """

    # Closures to break up functions for readability

    def return_with_error_code(msg: str = ""):
        if cur_fp is not None:
            cur_fp.close()
        if msg:
            print(f"[p2p_copy] receive(): {msg}")
        return 4

    async def handle_enc_manifest(o: dict):
        try:
            nonce_hex = o.get("nonce")
            secure.nonce_hasher.next_hash(bytes.fromhex(nonce_hex))
            hidden = bytes.fromhex(o["hidden_manifest"])
            manifest_str = secure.decrypt_chunk(hidden).decode()
            o = loads(manifest_str)
            await handle_manifest(o)  # Delegate to plain handler
        except Exception as e:
            raise ValueError(f"Failed to decrypt manifest: {e}")

    async def handle_manifest(o: dict):
        resume = o.get("resume", False)
        if resume:
            entries = o.get("entries", [])
            reply_entries: List[ReceiverManifestEntry] = []

            for e in entries:
                try:
                    rel = Path(e["path"])
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
                except Exception:
                    continue  # Skip bad entries

            if encrypt:
                clear = ReceiverManifest(type="receiver_manifest", entries=reply_entries).to_json().encode()
                hidden = secure.encrypt_chunk(clear)
                reply = EncryptedReceiverManifest(
                    type="enc_receiver_manifest",
                    hidden_manifest=hidden.hex()
                ).to_json()
                await ws.send(reply)
            else:
                await ws.send(ReceiverManifest(type="receiver_manifest", entries=reply_entries).to_json())

    async def handle_enc_file(o: dict):
        try:
            hidden = bytes.fromhex(o["hidden_file"])
            file_str = secure.decrypt_chunk(hidden).decode()
            o = loads(file_str)
            await handle_file(o)
        except Exception as e:
            raise ValueError(f"Failed to decrypt file info: {e}")

    async def handle_file(o: dict):
        nonlocal cur_fp, cur_expected_size, cur_seq_expected, bytes_written, compressor, chained_checksum
        if cur_fp is not None:
            raise ValueError("Got new file while previous still open")
        try:
            rel_path = o["path"]
            total_size: int = o.get("size")
            compression = o.get("compression", "none")
            append_from: int = o.get("append_from", 0)
        except Exception:
            raise ValueError(f"Bad file header: {o}")

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
                expected_remaining = total_size

        cur_fp = dest.open(open_mode)
        cur_expected_size = expected_remaining
        cur_seq_expected = 0
        bytes_written = 0
        compressor.set_decompression(compression)
        chained_checksum = ChainedChecksum()

    async def handle_file_eof(o: dict):
        nonlocal cur_fp
        if cur_fp is None:
            raise ValueError("Got file_eof without open file")
        if cur_expected_size is not None and bytes_written != cur_expected_size:
            raise ValueError(f"Size mismatch: {bytes_written} != {cur_expected_size}")
        cur_fp.close()
        cur_fp = None

    async def handle_chunk():
        nonlocal bytes_written, cur_seq_expected
        if cur_fp is None:
            raise ValueError("Unexpected binary data without open file")
        seq, chain, payload = unpack_chunk(frame)
        if seq != cur_seq_expected:
            raise ValueError(f"Sequence mismatch: {seq} != {cur_seq_expected}")

        raw_payload = secure.decrypt_chunk(payload) if encrypt else payload
        if chained_checksum.next_hash(raw_payload) != chain:
            raise ValueError("Chained checksum mismatch")

        chunk = compressor.decompress(raw_payload)
        await asyncio.to_thread(cur_fp.write, chunk)

        bytes_written += len(chunk)
        cur_seq_expected += 1

    async def handle_eof(o: dict):
        raise StopAsyncIteration  # Break the loop cleanly

    # Frame type dispatcher
    async def dispatch_frame():
        if isinstance(frame, (bytes, bytearray)):
            await handle_chunk()

        elif not isinstance(frame, str):
            raise ValueError("Unknown frame type")

        else:
            o = loads(frame)
            t = o.get("type")

            handlers = {
                "enc_manifest": handle_enc_manifest if encrypt else None,
                "manifest": handle_manifest if not encrypt else None,
                "enc_file": handle_enc_file if encrypt else None,
                "file": handle_file if not encrypt else None,
                "file_eof": handle_file_eof,
                "eof": handle_eof,
            }
            handler = handlers.get(t)
            if handler is None:
                raise ValueError(f"Unexpected control: {o}")
            await handler(o)

    # End of Closures

    out_dir = Path(out or ".")
    ensure_dir(out_dir)

    secure = SecurityHandler(code, encrypt)
    hello = Hello(type="hello", code_hash_hex=secure.code_hash.hex(), role="receiver").to_json()

    # Receiver state
    cur_fp: Optional[BinaryIO] = None
    cur_expected_size: Optional[int] = None
    cur_seq_expected = 0
    bytes_written = 0
    chained_checksum = ChainedChecksum()
    compressor = Compressor()
    resume_known: Dict[str, Tuple[int, bytes]] = {}

    async with connect(server, max_size=2**21, compression=None) as ws:
        await ws.send(hello)
        try:
            async for frame in ws:
                await dispatch_frame()
        except StopAsyncIteration:
            pass  # Normal EOF
        except ValueError as e:
            return return_with_error_code(str(e))

    if cur_fp is not None:
        return return_with_error_code("Stream ended while file open")
    return 0
