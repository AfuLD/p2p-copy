from __future__ import annotations
"""
Compression/Throughput bench (Phase 4 prep)

This test embeds lightly-modified relay + API shims at the top so we can:
- Toggle WebSocket permessage-deflate (on/off)
- Apply application-level compression (deflate/zlib/gzip/zstd) with levels
- Vary chunk size
- Simulate upload/download speeds by sleeping in the relay while piping

The rest of the project is imported normally.

Note: zstd is optional; test skips that variant if the `zstandard` module
is unavailable in the environment.
"""

import asyncio
import json
import os
import socket
import ssl
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, BinaryIO

# ----------------------------- relay (shim) -----------------------------
from websockets.asyncio.server import serve, ServerConnection
from websockets.asyncio.client import connect

WAITING: Dict[str, Tuple[str, ServerConnection]] = {}
LOCK = asyncio.Lock()

@dataclass
class Throttle:
    up_mbit: float  # sender->relay (upload at sender)
    down_mbit: float  # relay->receiver (download at receiver)

    @property
    def up_Bps(self) -> float:
        return self.up_mbit * 1_000_000 / 8.0

    @property
    def down_Bps(self) -> float:
        return self.down_mbit * 1_000_000 / 8.0


async def _pipe(a: ServerConnection, b: ServerConnection, bytes_per_sec: float) -> None:
    try:
        async for frame in a:
            # Simulate bandwidth limits based on frame size
            size = len(frame) if isinstance(frame, (bytes, bytearray)) else len(frame.encode("utf-8"))
            network_delay = (size / bytes_per_sec)

            # eithere a) calculate it
            global t0
            t0 -= network_delay

            # or b) actually sleep
            #time.sleep(network_delay)

            await b.send(frame)


    except Exception:
        pass
    finally:
        try:
            await b.close()
        except Exception:
            pass


async def _handle(ws: ServerConnection, throttle: Throttle) -> None:
    # 1) expect hello (text)
    try:
        raw = await ws.recv()
    except Exception:
        return
    if not isinstance(raw, str):
        await ws.close(code=1002, reason="First frame must be hello text"); return
    try:
        hello = json.loads(raw)
    except Exception:
        await ws.close(code=1002, reason="Bad hello json"); return
    if hello.get("type") != "hello":
        await ws.close(code=1002, reason="First frame must be hello"); return
    code_hash = hello.get("code_hash_hex")
    role = hello.get("role")
    if not code_hash or role not in {"sender","receiver"}:
        await ws.close(code=1002, reason="Bad hello"); return

    # 2) Pair by code_hash (exactly one sender + one receiver)
    peer: Optional[ServerConnection] = None
    async with LOCK:
        if code_hash in WAITING:
            other_role, other_ws = WAITING.pop(code_hash)
            if other_role == role:
                await other_ws.close(code=1013, reason="Duplicate role for code")
                await ws.close(code=1013, reason="Duplicate role for code")
                return
            peer = other_ws
        else:
            WAITING[code_hash] = (role, ws)

    if peer is None:
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            async with LOCK:
                if WAITING.get(code_hash, (None,None))[1] is ws:
                    WAITING.pop(code_hash, None)
        return

    # 3) Start bi-directional piping, apply asymmetric throttle
    # sender uploads to relay (ws role determines direction)
    t1 = asyncio.create_task(_pipe(ws, peer, throttle.up_Bps))
    t2 = asyncio.create_task(_pipe(peer, ws, throttle.down_Bps))
    done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()


async def run_relay(*, host: str, port: int, use_tls: bool = False,
                    certfile: Optional[str] = None, keyfile: Optional[str] = None,
                    ws_compression: bool = False,
                    throttle: Throttle) -> None:
    ssl_ctx = None
    if use_tls:
        if not certfile or not keyfile:
            raise RuntimeError("TLS requested but certfile/keyfile missing")
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(certfile, keyfile)

    compression = "deflate" if ws_compression else None

    async with serve(lambda ws: _handle(ws, throttle), host, port, max_size=None, ssl=ssl_ctx, compression=compression):
        await asyncio.Future()


# ----------------------------- API (shim) -----------------------------
# We build on project modules where possible.

from p2p_copy.security import ChainedChecksum, SecurityHandler
from p2p_copy.io_utils import read_in_chunks, compute_chain_up_to
from p2p_copy.io_utils import iter_manifest_entries, ensure_dir
from p2p_copy.protocol import (
    Hello, Manifest, ManifestEntry, EOF,
    file_begin, FILE_EOF, pack_chunk, unpack_chunk
)

import zlib
try:
    import zstandard as zstd  # optional
except Exception:  # pragma: no cover
    zstd = None

@dataclass
class AppCompression:
    algo: str  # "none" | "deflate" | "zlib" | "gzip" | "zstd"
    level: int

    def compressor(self):
        if self.algo == "none":
            return None
        if self.algo == "deflate":
            return zlib.compressobj(self.level, zlib.DEFLATED, wbits=-15)
        if self.algo == "zlib":
            return zlib.compressobj(self.level, zlib.DEFLATED, wbits=15)
        if self.algo == "gzip":
            return zlib.compressobj(self.level, zlib.DEFLATED, wbits=31)
        if self.algo == "zstd":
            if zstd is None:
                raise RuntimeError("zstandard module not available")
            return zstd.ZstdCompressor(level=self.level)
        raise ValueError(self.algo)

    def decompressor(self):
        if self.algo == "none":
            return None
        if self.algo == "deflate":
            return zlib.decompressobj(wbits=-15)
        if self.algo == "zlib":
            return zlib.decompressobj(wbits=15)
        if self.algo == "gzip":
            return zlib.decompressobj(wbits=31)
        if self.algo == "zstd":
            if zstd is None:
                raise RuntimeError("zstandard module not available")
            return zstd.ZstdDecompressor()
        raise ValueError(self.algo)


async def api_send(server: str, code: str, sources: List[str], *,
                   app_comp: AppCompression, chunk_size: int,
                   ws_compression: bool) -> int:
    # Build manifest
    entries: List[ManifestEntry] = []
    resolved: List[Tuple[Path, Path, int]] = list(iter_manifest_entries(sources))
    if not resolved:
        print("[p2p_copy] send(): no files provided"); return 2
    for abs_p, rel_p, size in resolved:
        entries.append(ManifestEntry(path=rel_p.as_posix(), size=size))

    secure = SecurityHandler(code, False)
    hello = Hello(type="hello", code_hash_hex=secure.code_hash.hex(), role="sender").to_json()
    manifest = Manifest(type="manifest", entries=entries).to_json()

    compression = "deflate" if ws_compression else None

    async with connect(server, max_size=None, compression=compression) as ws:
        await ws.send(hello)
        await ws.send(manifest)

        # announce per-file compression settings
        comp_announce = json.dumps({"type": "comp", "algo": app_comp.algo, "level": app_comp.level})

        # Track total input vs compressed output
        orig_bytes = 0
        comp_bytes = 0

        for abs_p, rel_p, size in resolved:
            await ws.send(file_begin(rel_p.as_posix(), size))
            last_send = ws.send(comp_announce)

            chained_checksum = ChainedChecksum()
            seq = 0

            if app_comp.algo == "zstd" and zstd is not None:
                cctx = zstd.ZstdCompressor(level=app_comp.level)
                with abs_p.open("rb") as fp:
                    async for chunk in read_in_chunks(fp, chunk_size=chunk_size):
                        orig_bytes += len(chunk)
                        # Each chunk compressed as its own zstd frame; concatenation is valid
                        payload = cctx.compress(chunk)
                        comp_bytes += len(payload)
                        frame: bytes = pack_chunk(seq, chained_checksum.next_hash(payload), payload)
                        await last_send
                        last_send = ws.send(frame)
                        seq += 1
            else:
                cobj = app_comp.compressor()
                with abs_p.open("rb") as fp:
                    async for chunk in read_in_chunks(fp, chunk_size=chunk_size):
                        orig_bytes += len(chunk)
                        if cobj is None:
                            payload = chunk
                        else:
                            payload = cobj.compress(chunk) + cobj.flush(zlib.Z_SYNC_FLUSH)
                        comp_bytes += len(payload)
                        frame: bytes = pack_chunk(seq, chained_checksum.next_hash(payload), payload)
                        await last_send
                        last_send = ws.send(frame)
                        seq += 1

            await last_send
            await ws.send(FILE_EOF)
        await ws.send(EOF)
        # After file loop, compute ratio
        if orig_bytes > 0:
            ratio = comp_bytes / orig_bytes
            print(f"[bench] algo={app_comp.algo}:{app_comp.level} "
                  f"original={orig_bytes} bytes, compressed={comp_bytes} bytes, "
                  f"ratio={ratio:.3f}")
    return 0


async def api_receive(server: str, code: str, *, out: Optional[str], ws_compression: bool) -> int:
    out_dir = Path(out or ".")
    ensure_dir(out_dir)

    secure = SecurityHandler(code, False)
    hello = Hello(type="hello", code_hash_hex=secure.code_hash.hex(), role="receiver").to_json()

    cur_fp: Optional[BinaryIO] = None
    cur_path: Optional[Path] = None
    cur_expected_size: Optional[int] = None
    cur_seq_expected = 0
    chained_checksum = ChainedChecksum()

    # default: no app compression unless announced
    active_algo = "none"
    dctx = None

    compression = "deflate" if ws_compression else None

    async with connect(server, max_size=None, compression=compression) as ws:
        await ws.send(hello)
        async for frame in ws:
            if isinstance(frame, bytes):
                if cur_fp is None:
                    print("[p2p_copy][test] unexpected binary frame"); return 4
                try:
                    seq, chain, payload = unpack_chunk(frame)
                except Exception as e:
                    print("[p2p_copy][test] bad chunk frame:", e); return 4
                if seq != cur_seq_expected:
                    print("[p2p_copy][test] bad seq", seq, cur_seq_expected); return 4
                expected_chain = chained_checksum.next_hash(payload)
                if chain != expected_chain:
                    print("[p2p_copy][test] chain mismatch"); return 4

                # decompress if configured
                if active_algo == "zstd" and dctx is not None:
                    payload = dctx.decompress(payload)
                elif dctx is not None:
                    payload = dctx.decompress(payload)

                cur_fp.write(payload)
                cur_seq_expected += 1
                continue

            # text frame
            try:
                o = json.loads(frame)
            except Exception:
                print("[p2p_copy][test] unexpected text", frame); return 4
            t = o.get("type")

            if t == "manifest":
                for e in o.get("entries", []):
                    rel = Path(e.get("path",""))
                    if rel.parent:
                        ensure_dir(out_dir / rel.parent)
                continue

            if t == "file":
                if cur_fp is not None:
                    print("[p2p_copy][test] new file while open"); return 4
                rel = Path(o.get("path",""))
                size = int(o.get("size",0))
                dest = out_dir / rel
                ensure_dir(dest.parent)
                cur_fp = dest.open("wb")
                cur_path = dest
                cur_expected_size = size
                cur_seq_expected = 0
                chained_checksum = ChainedChecksum()
                continue

            if t == "comp":
                active_algo = o.get("algo","none")
                level = int(o.get("level",0))
                if active_algo == "none":
                    dctx = None
                elif active_algo == "zstd":
                    if zstd is None:
                        return 4
                    dctx = zstd.ZstdDecompressor()
                elif active_algo in {"deflate","zlib","gzip"}:
                    wbits = {"deflate": -15, "zlib": 15, "gzip": 31}[active_algo]
                    dctx = zlib.decompressobj(wbits=wbits)
                else:
                    return 4
                continue

            if t == "file_eof":
                if cur_fp is None:
                    print("[p2p_copy][test] eof without file"); return 4
                cur_fp.flush(); cur_fp.close(); cur_fp = None
                continue

            if t == "eof":
                break

            if t == "hello":
                continue

            print("[p2p_copy][test] unexpected control", o); return 4

    if cur_fp is not None:
        print("[p2p_copy][test] stream ended while file open"); return 4
    return 0


# ----------------------------- helpers -----------------------------

def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ----------------------------- benchmark test -----------------------------

def test_compression_compute_chain_up_to():
    asyncio.run(async_compression_compute_chain_up_to())

async def async_compression_compute_chain_up_to():
    # Input corpus from ./test_resources
    corpus_root = Path(__file__).parent / ".." / "test_resources"
    corpus_root = corpus_root.resolve()
    if not corpus_root.exists():
        print("skip this test if no test_resources folder has been created")
        print(f"test_resources dir missing: {corpus_root}")
        return

    src = corpus_root

    t0 = time.perf_counter()
    total_size = 0
    total_size2 = 0
    for p in corpus_root.glob("**/*"):
        if p.is_file():
            size, _ = await compute_chain_up_to(p)
            total_size2 += size
            total_size += p.stat().st_size

    print(f"\nshould Compressed: {total_size // 2**20}MB, did compress: {total_size2 // 2**20}MB in {time.perf_counter() - t0:.3f}s")

def test_compression_matrix_single_run(tmp_path: Path):
    # Parameter sets
    ws_compress_options = [False] # should be false if test is local
    algo_level_pairs = [
        ("none", 0),
        ("zstd", 3),
        ("deflate", 6),
        #("zlib", 6),
        #("gzip", 6),
    ]
    chunk_kib_options = [1024]
    bandwidth_options = [
        # (upload, download in Mbit)
        #(2.4, 16),
        #(50, 250),
        (500, 1000),
    ]

    # Input corpus from ./test_resources
    corpus_root = Path(__file__).parent / ".." / "test_resources"
    corpus_root = corpus_root.resolve()
    if not corpus_root.exists():
        print("skip this test if no test_resources folder has been created")
        print(f"test_resources dir missing: {corpus_root}")
        return

    src = corpus_root

    results = []

    # Iterate over all combinations
    for ws_compress in ws_compress_options:
        for algo, level in algo_level_pairs:
            if algo == "zstd" and zstd is None:
                print(f"Skipping zstd test (zstandard not installed)")
                continue
            for chunk_kib in chunk_kib_options:
                for uplink_mbit, downlink_mbit in bandwidth_options:
                    out = tmp_path / f"out_ws{ws_compress}_algo{algo}_lvl{level}_chk{chunk_kib}_up{uplink_mbit}_down{downlink_mbit}"
                    out.mkdir()

                    host = "localhost"
                    port = _free_port()
                    server_url = f"ws://{host}:{port}"
                    code = f"bench-{os.getpid()}-{time.time_ns()}"

                    throttle = Throttle(up_mbit=uplink_mbit, down_mbit=downlink_mbit)

                    async def runner():
                        relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False,
                                                                   ws_compression=ws_compress, throttle=throttle))
                        try:
                            await asyncio.sleep(0.1)
                            recv_task = asyncio.create_task(api_receive(server=server_url, code=code, out=str(out), ws_compression=ws_compress))
                            await asyncio.sleep(0.1)

                            global t0
                            t0 = time.perf_counter()

                            rc_send = await api_send(server=server_url, code=code, sources=[str(src)],
                                                     app_comp=AppCompression(algo=algo, level=level),
                                                     chunk_size=chunk_kib * 1024,
                                                     ws_compression=ws_compress)
                            rc_recv = await asyncio.wait_for(recv_task, timeout=60)

                            dt = time.perf_counter() - t0
                            return rc_send, rc_recv, dt
                        finally:
                            relay_task.cancel()


                    rc_s, rc_r, seconds = asyncio.run(runner())

                    # Expect success
                    assert rc_s == 0 and rc_r == 0, f"Failed: ws_comp={ws_compress}, algo={algo}, level={level}, chunk={chunk_kib}KiB, net={uplink_mbit}/{downlink_mbit}Mbit"

                    # Compute bytes transferred (sum of actual output files)
                    total_bytes = 0
                    for p in out.rglob("*"):
                        if p.is_file():
                            total_bytes += p.stat().st_size

                    # Calculate metrics
                    mbit = total_bytes * 8 / 1_000_000
                    throughput = mbit / seconds if seconds > 0 else 0.0
                    results.append({
                        "ws_compress": ws_compress,
                        "algo": algo,
                        "level": level,
                        "chunk_kib": chunk_kib,
                        "uplink_mbit": uplink_mbit,
                        "downlink_mbit": downlink_mbit,
                        "mbit": mbit,
                        "seconds": seconds,
                        "throughput": throughput
                    })

                    # Lightweight sanity bound: expect >1 Mbit/s unless throttled to 10 Mbit/s
                    assert seconds < 6000, f"Timeout: ws_comp={ws_compress}, algo={algo}, level={level}, chunk={chunk_kib}KiB, net={uplink_mbit}/{downlink_mbit}Mbit"

    # Print summary of all results
    print("\n[bench] Summary of all test runs:")
    for result in results:
        print(f"[bench] ws_comp={result['ws_compress']} app={result['algo']}:{result['level']} "
              f"chunk={result['chunk_kib']}KiB net={result['uplink_mbit']}/{result['downlink_mbit']}Mbit: "
              f"sent={result['mbit']:.2f} Mbit in {result['seconds']:.3f}s → {result['throughput']:.2f} Mbit/s")

    # Optional: Assert aggregate condition if needed (e.g., at least one test ran)
    assert results, "No tests were executed"