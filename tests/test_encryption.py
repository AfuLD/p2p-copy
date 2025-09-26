from __future__ import annotations

import random
import socket
import subprocess
import time
from contextlib import closing
from pathlib import Path

import pytest

from p2p_copy import send as api_send, receive as api_receive, CompressMode


import asyncio
import json
import ssl
from typing import Dict, Tuple, Optional

from websockets.asyncio.server import serve, ServerConnection

from p2p_copy.protocol import READY

WAITING: Dict[str, Tuple[str, ServerConnection]] = {}  # code_hash -> (role, ws)
LOCK = asyncio.Lock()

async def _pipe(a: ServerConnection, b: ServerConnection) -> None:
    try:
        async for frame in a:
            # make sure that neither file name nor file content is unencrypted
            if "copy_file" in str(frame):
                print("message was not encrypted")
                raise
            await b.send(frame)
    except Exception:
        pass
    finally:
        try:
            await b.close()
        except Exception:
            pass

async def _handle(ws: ServerConnection) -> None:
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
                # two senders or two receivers — reject both
                await other_ws.close(code=1013, reason="Duplicate role for code")
                await ws.close(code=1013, reason="Duplicate role for code")
                return
            peer = other_ws
        else:
            WAITING[code_hash] = (role, ws)

    if peer is None:
        # wait until paired; then this handler exits when ws closes
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            async with LOCK:
                if WAITING.get(code_hash, (None,None))[1] is ws:
                    WAITING.pop(code_hash, None)
        return

    # 3) Start bi-directional piping

    t1 = asyncio.create_task(_pipe(ws, peer))
    t2 = asyncio.create_task(_pipe(peer, ws))

    # 4) Inform sender that pipe is ready
    await (ws if role == "sender" else other_ws).send(READY)
    await asyncio.sleep(0.2)
    done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()

def run_sync(host: str, port: int, use_tls: bool, certfile: Optional[str], keyfile: Optional[str]) -> None:
    asyncio.run(run_relay(host=host, port=port, use_tls=use_tls, certfile=certfile, keyfile=keyfile))

async def run_relay(
        *, host: str, port: int,
        use_tls: bool = True,
        certfile: Optional[str] = None,
        keyfile: Optional[str] = None,
) -> None:
    ssl_ctx = None
    if use_tls:
        if not certfile or not keyfile:
            raise RuntimeError("TLS requested but certfile/keyfile missing")
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(certfile, keyfile)

    scheme = "wss" if ssl_ctx else "ws"
    print(f"Relay listening on {scheme}://{host}:{port}")
    async with serve(_handle, host, port, max_size=None, ssl=ssl_ctx):
        await asyncio.Future()  # run forever



def _free_port() -> int:
    """Return a free TCP port for local WS tests."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _build_payload(keyword: str, encrypt: bool, compress: str) -> str:
    """
    Build the file payload used in tests.
    Requirements:
      - must include the literal phrase "copy_file"
      - must include the values for encrypt and compress
      - should start with a keyword for quick identification
    """
    return (
            f"keyword:{keyword}\n"
            f"copy_file\n"
            f"encrypt={encrypt}\n"
            f"compress={compress}\n"
    )


# ---------- API TESTS ----------

@pytest.mark.parametrize("mode",["off","on","auto"])
def test_api_encrypt_with_compression_ws(tmp_path: Path, mode: str):
    asyncio.run(async_test_api_encrypt_with_compression_ws(tmp_path, mode))

async def async_test_api_encrypt_with_compression_ws(tmp_path: Path, mode: str):
    """
    End-to-end over WS with encryption + compression.
    Ensures payload survives, and markers for encrypt/compress are present.
    """
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    code = f"enc+comp-{mode}"

    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    await asyncio.sleep(0.1)

    src = tmp_path / "enc_comp_copy_file.txt"
    src.write_text(_build_payload("ENCRYPTION_WITH_COMPRESSION", encrypt=True, compress=mode), encoding="utf-8")
    out_dir = tmp_path / "out"

    recv_task = asyncio.create_task(
        api_receive(code=code, server=server_url, encrypt=True, out=str(out_dir))
    )
    await asyncio.sleep(0.05)
    send_rc = await api_send(
        files=[str(src)], code=code, server=server_url, encrypt=True, compress=CompressMode[mode]
    )
    recv_rc = await asyncio.wait_for(recv_task, timeout=3.0)

    relay_task.cancel()

    assert send_rc == 0 and recv_rc == 0
    dest = out_dir / "enc_comp_copy_file.txt"
    out_text = dest.read_text(encoding="utf-8")
    in_text = src.read_text(encoding="utf-8")
    assert out_text.startswith("keyword:ENCRYPTION_WITH_COMPRESSION")
    assert "copy_file" in out_text
    assert "encrypt=True" in out_text
    assert f"compress={mode}" in out_text
    # sanity: exact byte-for-byte text match after round-trip
    assert out_text == in_text


def test_api_encrypt_flag_mismatch_fails(tmp_path: Path):
    asyncio.run(async_test_api_encrypt_flag_mismatch_fails(tmp_path))

async def async_test_api_encrypt_flag_mismatch_fails(tmp_path: Path):
    """
    Sender uses encrypt=True while receiver uses encrypt=False (or vice versa).
    Expect a failure signal (non-zero return code or pairing failure).
    """
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    code = "enc-mismatch"

    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    await asyncio.sleep(0.1)

    src = tmp_path / "mismatch_copy_file.txt"
    # Still include required markers, though this transfer should not succeed.
    src.write_text(_build_payload("MISMATCH_TEST", encrypt=True, compress=CompressMode.auto), encoding="utf-8")
    out_dir = tmp_path / "out"

    recv_task = asyncio.create_task(api_receive(code=code, server=server_url, encrypt=True, out=str(out_dir)))
    await asyncio.sleep(0.1)
    send_task = asyncio.create_task(api_send(files=[str(src)], code=code, server=server_url, encrypt=False))

    try:
        failed_to_send = (await asyncio.wait_for(send_task, timeout=1.0)) != 0
    except asyncio.TimeoutError:
        failed_to_send = True

    try:
        failed_to_receive = (await asyncio.wait_for(recv_task, timeout=0.1)) != 0
    except asyncio.TimeoutError:
          failed_to_receive = True

    relay_task.cancel()
    assert (failed_to_send and failed_to_receive), "Encryption flag mismatch should not succeed"


# ---------- CLI TESTS ----------

@pytest.mark.parametrize("mode",["off","on","auto"])
def test_cli_encrypt_with_compression_ws(tmp_path: Path, mode: str):
    """
    End-to-end via CLI with --encrypt and --compress <mode>.
    Confirms presence of 'copy_file' and the exact encrypt/compress values.
    """
    host = "localhost"
    port = _free_port()
    code = f"cli-enc-comp-{mode}"

    relay_proc = subprocess.Popen(
        ["p2p-copy", "run-relay-server", host, str(port), "--no-tls"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(0.15)

    out_dir = tmp_path / "downloads"
    recv_proc = subprocess.Popen(
        ["p2p-copy", "receive", f"ws://{host}:{port}", code, "--encrypt", "--out", str(out_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(0.1)

    src = tmp_path / "enc_comp_cli_copy_file.txt"
    src.write_text(_build_payload("CLI_ENCRYPT_WITH_COMPRESSION", encrypt=True, compress=mode), encoding="utf-8")

    send_cmd = [
        "p2p-copy", "send", f"ws://{host}:{port}", code, str(src),
        "--encrypt", "--compress", mode
    ]
    send_proc = subprocess.run(
        send_cmd,
        capture_output=True,
        text=True,
        timeout=2,
    )
    assert send_proc.returncode == 0, f"send CLI failed: {send_proc.stdout}\n{send_proc.stderr}"

    recv_rc = recv_proc.wait(timeout=20)
    assert recv_rc == 0, f"receive CLI failed: {recv_proc.stdout and recv_proc.stdout.read()}"

    dest = out_dir / "enc_comp_cli_copy_file.txt"
    text = dest.read_text(encoding="utf-8")
    assert text.startswith("keyword:CLI_ENCRYPT_WITH_COMPRESSION")
    assert "copy_file" in text
    assert "encrypt=True" in text
    assert f"compress={mode}" in text  # exact mode string passed on CLI

    relay_proc.terminate()
    try:
        relay_proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        relay_proc.kill()



def _compressible_bytes(n: int) -> bytes:
    # long runs of the same few chars -> easy to compress
    return (b"AAAABBBBCCCCDDDDEEEE" * ((n // 20) + 1))[:n]

def _incompressible_bytes(n: int) -> bytes:
    # pseudo-random noise -> hard to compress
    rnd = random.Random(42)
    return bytes(rnd.getrandbits(8) for _ in range(n))

def _mk_files(base: Path, layout: dict[str, bytes]) -> None:
    for rel, content in layout.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

def test_transfer_timings_for_compression_modes_encrypted(tmp_path):
    """
    Measure time to receive for compressible vs incompressible payloads across
    compression modes. We don't assert hard numbers—only sensible orderings:

    - For highly compressible data:  on * 1.5 <=  off  (on should be faster)
      and auto ≈ on.
    - For incompressible data:       off <= on   (on shouldn't be faster)
      and auto ≈ off.
    """
    # Size large enough to see a difference(~30 MiB)
    SIZE = 30 * 1024 * 1024

    comp = _compressible_bytes(SIZE)
    incomp = _incompressible_bytes(SIZE)

    async def run_all():
        from p2p_copy_server.relay import run_relay
        host = "localhost"
        port = _free_port()
        server_url = f"ws://{host}:{port}"
        relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
        await asyncio.sleep(0.1)

        results = {}
        for label, payload in [("compressible", comp), ("incompressible", incomp)]:
            results[label] = {}
            for mode in (CompressMode.off,  CompressMode.auto, CompressMode.on):
                # warm up
                await asyncio.sleep(0)
                elapsed = await _time_one_transfer(payload, mode, tmp_path, f"{label}", server_url)
                results[label][mode.value] = elapsed

        relay_task.cancel()
        return results

    results = asyncio.run(run_all())

    # Pretty-print timings into test output for debugging
    print("\nTiming results with encryption (seconds):")
    for label, modes in results.items():
        print(f"  {label}: " + ", ".join(f"{m}={t:.3f}" for m, t in modes.items()))

    comp_off = results["compressible"]["off"]
    comp_on  = results["compressible"]["on"]
    comp_auto = results["compressible"]["auto"]

    incomp_off = results["incompressible"]["off"]
    incomp_on  = results["incompressible"]["on"]
    incomp_auto = results["incompressible"]["auto"]

    # --- Assertions with slack to avoid flakiness ---
    # Compressible should benefit from compression
    assert comp_on <= comp_off * 0.9, f"Expected 'on' to be faster on compressible data (on={comp_on:.3f}s, off={comp_off:.3f}s)"
    assert comp_on * 0.9 - 0.01 <= comp_auto <=  comp_off * 0.9, \
        f"Expected 'auto' ~ 'on' for compressible (auto={comp_auto:.3f}s, on={comp_on:.3f}s)"

    # Incompressible should not benefit; 'off' should be as fast or faster
    assert incomp_off * 0.9 - 0.01 <= incomp_on, f"Expected 'off' to be not slower on incompressible (off={incomp_off:.3f}s, on={incomp_on:.3f}s)"
    assert incomp_off * 0.9 - 0.01 <= incomp_auto <= incomp_on * 1.1 + 0.01, \
        f"Expected 'auto' ~ 'off' for incompressible (auto={incomp_auto:.3f}s, off={incomp_off:.3f}s)"


async def _time_one_transfer(payload: bytes, mode: CompressMode, tmp_path: Path, label: str, server_url) -> float:
    """Run a single send/receive and return elapsed seconds."""

    code = f"timing-{label}-{mode.value}"

    src = tmp_path / f"src-{label}-{mode.value}"
    out = tmp_path / f"out-{label}-{mode.value}"
    _mk_files(src, {"file.bin": payload})

    recv_task = asyncio.create_task(api_receive(server=server_url, code=code, encrypt=True, out=str(out)))
    await asyncio.sleep(0.1)  # ensure receiver is listening

    t0 = time.monotonic()
    send_rc = await api_send(server=server_url, code=code, files=[str(src)], compress=mode, encrypt=True)
    recv_rc = await asyncio.wait_for(recv_task, timeout=2.0)
    elapsed = time.monotonic() - t0

    assert send_rc == 0
    assert recv_rc == 0
    assert (out / f"src-{label}-{mode.value}" / "file.bin").read_bytes() == payload
    return elapsed
