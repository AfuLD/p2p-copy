from __future__ import annotations

import asyncio
import json
import random
import socket
import ssl
import subprocess
import time
from contextlib import closing
from pathlib import Path
from typing import Dict, Tuple, Optional

import pytest
from websockets.asyncio.server import serve, ServerConnection

# API entry points
from p2p_copy import send as api_send, receive as api_receive
from p2p_copy.compressor import CompressMode
from p2p_copy.io_utils import CHUNK_SIZE
from p2p_copy.protocol import READY


def use_production_logger():
    # Custom logging for concise handshake errors
    import logging
    relay_logger = logging.getLogger("websockets.server")

    def filter_handshake(record):
        if "opening handshake failed" in record.getMessage():
            record.exc_info = None  # Suppress traceback
            record.exc_text = None  # Also clear formatted exception
        return True  # Log the (modified) record

    # Clear existing handlers/filters if needed (optional, for clean setup)
    relay_logger.handlers.clear()
    relay_logger.filters.clear()
    relay_logger.addFilter(filter_handshake)

    # Set a formatter for nicer output
    handler = logging.StreamHandler()  # Defaults to stderr
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - relay - %(message)s')
    handler.setFormatter(formatter)
    relay_logger.addHandler(handler)
    relay_logger.setLevel(logging.INFO)

WAITING: Dict[str, Tuple[str, ServerConnection]] = {}  # code_hash -> (role, ws)
LOCK = asyncio.Lock()

async def _pipe(a: ServerConnection, b: ServerConnection) -> None:
    try:
        async for frame in a:
            await asyncio.sleep(len(frame)/ 10 / 2**20) # simulate network delay
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

    # wait for one side to finish
    done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)

    # give the slower side up to 1 second to finish
    sleep_task = asyncio.create_task(asyncio.sleep(1.0))
    done2, pending2 = await asyncio.wait(pending | {sleep_task}, return_when=asyncio.FIRST_COMPLETED)

    # cancel whatever is still pending (excluding the sleep_task)
    for t in pending2:
        if t is not sleep_task:
            t.cancel()

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
    print(f"\nRelay listening on {scheme}://{host}:{port}")

    if host != "localhost":
        use_production_logger()

    async with serve(_handle, host, port, max_size=None, ssl=ssl_ctx, compression=None):
        await asyncio.Future()  # run forever


# ---------- helpers (mirrored style) ----------

def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def _mk_files(base: Path, layout: dict[str, bytes]) -> None:
    for rel, content in layout.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

def _fixed_bytes(n: int) -> bytes:
    # Fixed pattern for reproducible checksums
    return b"ABCDEFG" * n

def _make_bytes(n: int) -> bytes:
    rnd = random.Random(42)
    return bytes(rnd.getrandbits(8) for _ in range(n))

# ---------- unit-ish: end-to-end resume API ----------

@pytest.mark.parametrize("sender_resume", [True, False])
def test_api_resume_cases_end_to_end(tmp_path, sender_resume):
    asyncio.run(async_test_api_resume_cases_end_to_end(tmp_path, sender_resume))

async def async_test_api_resume_cases_end_to_end(tmp_path: Path, sender_resume: bool):
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    code = f"resume-api-{sender_resume}"

    src = tmp_path / "src"
    out = tmp_path / "out"

    # 2 MiB file: exactly 2 chunks
    payload = _fixed_bytes(2 * CHUNK_SIZE//7)
    rel = "big.bin"
    _mk_files(src, {rel: payload})

    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    try:
        await asyncio.sleep(0.1)

        # First transfer: full send to empty receiver
        recv_task1 = asyncio.create_task(
            api_receive(server=server_url, code=code, encrypt=False, out=str(out))
        )
        await asyncio.sleep(0.1)
        send_rc1 = await api_send(server=server_url, code=code, files=[str(src)], compress=CompressMode.off, resume=sender_resume)
        recv_rc1 = await asyncio.wait_for(recv_task1, timeout=15.0)

        assert send_rc1 == 0
        assert recv_rc1 == 0
        assert (out / "src" / rel).read_bytes() == payload

        # Now, prepare cases on receiver side
        cases = [
            ("full_skip", lambda f: f, "skip if sender_resume=True"),
            ("partial_resume", lambda f: f.write_bytes(f.read_bytes()[:CHUNK_SIZE]), "resume if sender_resume=True"),
            ("mismatch_overwrite", lambda f: f.write_bytes(f.read_bytes()[:-1] + b"B"), "full send always"),
        ]

        for case_name, prep, desc in cases:
            case_code = f"{code}-{case_name}"
            case_out = out / case_name
            case_out.mkdir()
            # Copy full received to case_out
            case_src_dir = case_out / "src"
            case_src_dir.mkdir(exist_ok=True)
            case_out_file = case_src_dir / rel
            case_out_file.write_bytes(payload)

            # Prepare receiver state
            prep(case_out_file)

            # Second transfer
            recv_task2 = asyncio.create_task(
                api_receive(server=server_url, code=case_code, encrypt=False, out=str(case_out))
            )
            await asyncio.sleep(0.1)
            send_rc2 = await api_send(server=server_url, code=case_code, files=[str(src)], compress=CompressMode.off, resume=sender_resume)
            try:
                recv_rc2 = await asyncio.wait_for(recv_task2, timeout=1.0)
            except asyncio.TimeoutError:
                recv_task2.cancel()
                raise

            assert send_rc2 == 0
            assert recv_rc2 == 0

            # Verify final file is always the sender's payload (integrity)
            assert (case_out / "src" / rel).read_bytes() == payload, f"Integrity failed for {desc} (sender_resume={sender_resume})"

    finally:
        relay_task.cancel()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(relay_task, timeout=0.1)


# ---------- end-to-end CLI: true / false ----------

@pytest.mark.parametrize("resume_flag", ["true", "false"])
def test_cli_resume_modes(tmp_path, resume_flag):
    """
    Smoke test CLI for resume true/false. Assumes --resume <true|false> only for send.
    """
    host = "localhost"
    port = _free_port()
    code = f"resume-cli-{resume_flag}"

    src = tmp_path / "src"
    out = tmp_path / "out"
    payload = _fixed_bytes(CHUNK_SIZE * 2//7)
    _mk_files(src, {"file.bin": payload})

    relay_proc = subprocess.Popen(
        ["p2p-copy", "run-relay-server", host, str(port), "--no-tls"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        time.sleep(0.1)

        # First transfer: full
        recv_proc1 = subprocess.Popen(
            ["p2p-copy", "receive", f"ws://{host}:{port}", code, "--out", str(out)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        time.sleep(0.1)
        send_run1 = subprocess.run(
            ["p2p-copy", "send", f"ws://{host}:{port}", code, str(src), "--compress", "off", "--resume", "false"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        assert send_run1.returncode == 0
        recv_rc1 = recv_proc1.wait(timeout=10)
        assert recv_rc1 == 0

        # Second transfer: test resume
        out_file = out / "src" / "file.bin"
        # For partial: truncate
        out_file.write_bytes(out_file.read_bytes()[:CHUNK_SIZE])

        recv_proc2 = subprocess.Popen(
            ["p2p-copy", "receive", f"ws://{host}:{port}", code, "--out", str(out)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        time.sleep(0.1)
        send_run2 = subprocess.run(
            ["p2p-copy", "send", f"ws://{host}:{port}", code, str(src), "--compress", "off", "--resume", resume_flag],
            capture_output=True,
            text=True,
            timeout=1,
        )
        assert send_run2.returncode == 0
        recv_rc2 = recv_proc2.wait(timeout=10)
        assert recv_rc2 == 0

        # Integrity
        assert (out / "src" / "file.bin").read_bytes() == payload

    finally:
        relay_proc.terminate()
        try:
            relay_proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            relay_proc.kill()


# ---------- behavioral smoke: resume should *tend* to transfer less when possible ----------

@pytest.mark.parametrize("encrypt", [False, True])
def test_resume_mode_prefers_existing(tmp_path, encrypt):
    """
    Behavior check: measure transfer times for full vs resume scenarios.
    """
    asyncio.run(_timing_resume_scenarios(tmp_path,encrypt))

async def _timing_resume_scenarios(tmp_path: Path, encrypt):
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    await asyncio.sleep(0.1)

    # 4 MiB: 4 chunks
    FULL_SIZE = 4 * CHUNK_SIZE //7 - 113
    payload = _fixed_bytes(FULL_SIZE)

    # Baseline: full send time
    code_base = "timing-full"
    src_base = tmp_path / "src"
    out_base = tmp_path / "out-full"
    _mk_files(src_base, {"file.bin": payload})
    t_full = await _time_one_transfer(payload, src_base, out_base, server_url, code_base, resume=False, encrypt=encrypt)

    # Skip: pre-existing full match
    code_skip = "timing-skip"
    out_skip = tmp_path / "out-skip"
    out_skip.mkdir()
    out_skip_src = out_skip / "src"
    out_skip_src.mkdir(exist_ok=True)
    (out_skip_src / "file.bin").write_bytes(payload)  # simulate existing
    t_skip = await _time_one_transfer(payload, src_base, out_skip, server_url, code_skip, resume=True, encrypt=encrypt)

    # Partial: pre-existing first 2 chunks
    code_partial = "timing-partial"
    out_partial = tmp_path / "out-partial"
    out_partial.mkdir()
    out_partial_src = out_partial / "src"
    out_partial_src.mkdir(exist_ok=True)
    partial_payload = payload[:2 * CHUNK_SIZE - 371]
    (out_partial_src / "file.bin").write_bytes(partial_payload)
    t_partial = await _time_one_transfer(payload, src_base, out_partial, server_url, code_partial, resume=True, encrypt=encrypt)

    # Mismatch: pre-existing but altered
    code_mismatch = "timing-mismatch"
    out_mismatch = tmp_path / "out-mismatch"
    out_mismatch.mkdir()
    out_mismatch_src = out_mismatch / "src"
    out_mismatch_src.mkdir(exist_ok=True)
    altered = payload[:-1] + b"B"
    (out_mismatch_src / "file.bin").write_bytes(altered)
    t_mismatch = await _time_one_transfer(payload, src_base, out_mismatch, server_url, code_mismatch, resume=True, encrypt=encrypt)

    relay_task.cancel()

    # Pretty-print
    print(f"\nTiming results for resume with {encrypt=}(seconds):")
    print(f"  full: {t_full:.3f}")
    print(f"  skip: {t_skip:.3f}")
    print(f"  partial (half): {t_partial:.3f}")
    print(f"  mismatch (full): {t_mismatch:.3f}")

    # Assertions with slack (network variability)
    # Skip should be near-instant
    assert t_skip < 1.0, f"Skip took too long: {t_skip:.3f}s"
    # Partial ~ half of full
    assert t_full * 0.4 <= t_partial <= t_full * 0.7, f"Partial not ~half: full={t_full:.3f}, partial={t_partial:.3f}"
    # Mismatch ~ full
    assert abs(t_mismatch - t_full) < t_full * 0.3, f"Mismatch not ~full: full={t_full:.3f}, mismatch={t_mismatch:.3f}"


async def _time_one_transfer(payload: bytes, src_dir: Path, out_dir: Path, server_url: str, code: str, resume: bool, encrypt: bool) -> float:
    """Run a send/receive (API or simulate CLI via API) and return elapsed seconds."""
    # Use API for timing

    recv_task = asyncio.create_task(
        api_receive(server=server_url, code=code, encrypt=encrypt, out=str(out_dir))
    )
    await asyncio.sleep(0.1)

    t0 = time.monotonic()
    send_rc = await api_send(server=server_url, code=code, files=[str(src_dir)], compress=CompressMode.off, resume=resume, encrypt=encrypt)
    recv_rc = await asyncio.wait_for(recv_task, timeout=1.0)
    elapsed = time.monotonic() - t0

    assert send_rc == 0
    assert recv_rc == 0
    assert (out_dir / "src" / "file.bin").read_bytes() == payload
    return elapsed




@pytest.mark.parametrize("encrypt", [False,True])
def test_interrupt_during_transfer(tmp_path, encrypt):
    asyncio.run(async_test_interrupt_during_transfer(tmp_path, encrypt))

async def async_test_interrupt_during_transfer(tmp_path: Path, encrypt: bool):
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    code_partial = f"interrupt-{encrypt}"
    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    await asyncio.sleep(0.1)

    try:
        src = tmp_path / "src"
        out = tmp_path / "out"
        # 3 chunks worth for clear partial
        payload = _fixed_bytes(10 * CHUNK_SIZE // 7)
        rel = "big.bin"
        _mk_files(src, {rel: payload})

        # First: partial transfer via interruption
        out.mkdir(exist_ok=True)
        recv_task_partial = asyncio.create_task(
            api_receive(server=server_url, code=code_partial, encrypt=encrypt, out=str(out))
        )
        await asyncio.sleep(0.1)
        send_task_partial = asyncio.create_task(
            api_send(
                server=server_url, code=code_partial, files=[str(src)],
                compress=CompressMode.off, resume=False, encrypt=encrypt
            )
        )

        # Simulate interruption after ~1-2 chunks (based on relay delay)
        await asyncio.sleep(0.01 if not encrypt else 0.03)  # Adjust if needed for ~1 chunk
        send_task_partial.cancel()
        try:
            await send_task_partial  # Wait for cancel to propagate
        except asyncio.CancelledError:
            pass

        # Receiver should error out but save partial file
        try:
            await asyncio.wait_for(recv_task_partial, timeout=1.0)
        except:
            # Expected: connection closed, task fails
            pass

        partial_file = out / "src" / rel
        assert partial_file.exists()
        partial_content = partial_file.read_bytes()
        # Should have at least 1 chunk, less than full
        assert 0 < len(partial_content), "partial_content empty"
        assert len(partial_content) < len(payload), "partial_content complete"
        # Prefix should match (no corruption)
        assert partial_content == payload[:len(partial_content)]

        # Now resume: second transfer should append/complete
        # new pairing with resume=True
        code_resume = f"resume-{encrypt}"
        recv_task_resume = asyncio.create_task(
            api_receive(server=server_url, code=code_resume, encrypt=encrypt, out=str(out))
        )
        await asyncio.sleep(0.05)
        send_rc_resume = await api_send(
            server=server_url, code=code_resume, files=[str(src)],
            compress=CompressMode.off, resume=True, encrypt=encrypt
        )
        recv_rc_resume = await asyncio.wait_for(recv_task_resume, timeout=1.0)

        assert send_rc_resume == 0
        assert recv_rc_resume == 0
        # Now full file
        assert (out / "src" / rel).read_bytes() == payload

    finally:
        relay_task.cancel()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(relay_task, timeout=0.1)


@pytest.mark.parametrize("encrypt", [False, True])
def test_interrupt_receiver_saves_partial(tmp_path, encrypt):
    asyncio.run(async_test_interrupt_receiver_saves_partial(tmp_path, encrypt))

async def async_test_interrupt_receiver_saves_partial(tmp_path: Path, encrypt: bool):
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    code_partial = f"recv-interrupt-{encrypt}"
    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    await asyncio.sleep(0.1)

    try:
        src = tmp_path / "src"
        out = tmp_path / "out"
        # 3 chunks
        payload = _fixed_bytes(3 * CHUNK_SIZE // 7)
        rel = "big.bin"
        _mk_files(src, {rel: payload})

        # Partial: interrupt receiver
        out.mkdir(exist_ok=True)
        recv_task_partial = asyncio.create_task(
            api_receive(server=server_url, code=code_partial, encrypt=encrypt, out=str(out))
        )
        await asyncio.sleep(0.1)
        send_task_partial = asyncio.create_task(
            api_send(
                server=server_url, code=code_partial, files=[str(src)],
                compress=CompressMode.off, resume=False, encrypt=encrypt
            )
        )

        # Interrupt receiver after partial
        await asyncio.sleep(0.3 if not encrypt else 0.32)  # Adjust if needed for ~1 chunk)
        recv_task_partial.cancel()
        try:
            await recv_task_partial
        except asyncio.CancelledError:
            pass

        # Sender should complete but receiver partial saved
        try:
            await asyncio.wait_for(send_task_partial, timeout=1.0)
        except asyncio.TimeoutError:
            # Sender might hang if receiver closes first, but with relay, it should close
            pass
        # Force close if needed, assume it finishes or errors

        partial_file = out / "src" / rel
        assert partial_file.exists()
        partial_content = partial_file.read_bytes()
        assert 0 < len(partial_content) < len(payload)
        assert partial_content == payload[:len(partial_content)]

        # Resume as before
        code_resume = f"recv-resume-{encrypt}"
        recv_task_resume = asyncio.create_task(
            api_receive(server=server_url, code=code_resume, encrypt=encrypt, out=str(out))
        )
        await asyncio.sleep(0.05)
        send_rc_resume = await api_send(
            server=server_url, code=code_resume, files=[str(src)],
            compress=CompressMode.off, resume=True, encrypt=encrypt
        )
        recv_rc_resume = await asyncio.wait_for(recv_task_resume, timeout=1.0)

        assert send_rc_resume == 0
        assert recv_rc_resume == 0
        assert (out / "src" / rel).read_bytes() == payload

    finally:
        relay_task.cancel()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(relay_task, timeout=0.1)


@pytest.mark.parametrize("encrypt", [False,True])
def test_resume_after_arbitrary_interrupt(tmp_path, encrypt):
    """
    Test resume works even if previous session was interrupted at various points.
    Simulates multiple partials with different lengths.
    """
    asyncio.run(async_test_resume_after_arbitrary_interrupt(tmp_path, encrypt))

async def async_test_resume_after_arbitrary_interrupt(tmp_path: Path, encrypt: bool):
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    await asyncio.sleep(0.1)

    try:
        src = tmp_path / "src"
        out = tmp_path / "out"

        payload = _fixed_bytes(13 * CHUNK_SIZE // 7)
        rel = "large.bin"
        _mk_files(src, {rel: payload})

        partial_file = out / "src" / rel
        len_partial_bytes = 0

        print(f"multi-interrupt with {encrypt=}")
        for i in range(5):
            code_partial = f"multi-interrupt-{i}-{encrypt}"

            # Transfer up to target_partial by timing
            recv_task = asyncio.create_task(
                api_receive(server=server_url, code=code_partial, encrypt=encrypt, out=str(out))
            )
            await asyncio.sleep(0.1)
            send_task = asyncio.create_task(
                api_send(
                    server=server_url, code=code_partial, files=[str(src)],
                    compress=CompressMode.off, resume=True, encrypt=encrypt
                )
            )

            # Sleep to approx target_partial (scale time)
            await asyncio.sleep((0.001 if not encrypt else 0.021) + (i / 100))  # Adjust if needed for ~1 chunk)
            send_task.cancel()
            try:
                await send_task
            except asyncio.CancelledError:
                pass

            try:
                await asyncio.wait_for(recv_task, timeout=1)
            except:
                pass

            if partial_file.exists():
                partial_bytes = partial_file.read_bytes()
                len_partial_bytes = len(partial_bytes)
                assert partial_bytes == payload[:len(partial_bytes)]

            print(f"attempt: {i}, copied: {len_partial_bytes / len(payload) * 100:.0f} %")
            if len_partial_bytes == len(payload):
                break
        else:
            assert partial_file.exists() and 0 < len_partial_bytes <=  len(payload), "nothing has been sent"

        # Final resume: should append from last partial to full
        code_final = f"final-resume-{encrypt}"
        recv_task_final = asyncio.create_task(
            api_receive(server=server_url, code=code_final, encrypt=encrypt, out=str(out))
        )
        await asyncio.sleep(0.05)
        send_rc_final = await api_send(
            server=server_url, code=code_final, files=[str(src)],
            compress=CompressMode.off, resume=True, encrypt=encrypt
        )
        recv_rc_final = await asyncio.wait_for(recv_task_final, timeout=1)

        assert send_rc_final == 0
        assert recv_rc_final == 0
        assert (out / "src" / rel).read_bytes() == payload

    finally:
        relay_task.cancel()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(relay_task, timeout=0.1)


@pytest.mark.parametrize("encrypt", [False, True])
@pytest.mark.parametrize("compress", [CompressMode.off, CompressMode.on])
def test_copy_resume_encrypt_and_compress(tmp_path: Path, encrypt: bool, compress: CompressMode):
    asyncio.run(copy_resume_encrypt_and_compress(tmp_path, encrypt, compress))

async def copy_resume_encrypt_and_compress(tmp_path: Path, encrypt: bool, compress: CompressMode):
    """Check that resume works with/without compression and encryption."""

    port = _free_port()
    host = "localhost"
    server_url = f"ws://{host}:{port}"
    code = "resume-test"

    # Start relay server
    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    await asyncio.sleep(0.2)  # give it time to bind

    # Create source file
    src_file = tmp_path / "src.bin"
    data = _make_bytes(2200_007)  # ~2200 KB
    src_file.write_bytes(data)

    # Receiver dir
    recv_dir = tmp_path / "recv"
    recv_dir.mkdir()

    # --- Case 1: no file present yet ---
    t_recv = asyncio.create_task(api_receive(server_url, code, encrypt=encrypt, out=str(recv_dir)))
    t_send = asyncio.create_task(api_send(server_url, code, [str(src_file)], encrypt=encrypt, resume=True, compress=compress))

    # this will raise an Error if any return code is not 0
    assert not any(await asyncio.gather(t_recv, t_send))

    dest_file = recv_dir / "src.bin"
    assert dest_file.read_bytes() == data

    # --- Case 2: receiver already has full file -> sender skips ---
    t_recv = asyncio.create_task(api_receive(server_url, code, encrypt=encrypt, out=str(recv_dir)))
    t_send = asyncio.create_task(api_send(server_url, code, [str(src_file)], encrypt=encrypt, resume=True, compress=compress))
    assert not any(await asyncio.gather(t_recv, t_send))
    # File should be unchanged
    assert dest_file.read_bytes() == data

    # --- Case 3: receiver has partial file -> sender appends remainder ---
    half = len(data) // 2
    dest_file.write_bytes(data[:half])  # truncate to half
    t_recv = asyncio.create_task(api_receive(server_url, code, encrypt=encrypt, out=str(recv_dir)))
    t_send = asyncio.create_task(api_send(server_url, code, [str(src_file)], encrypt=encrypt, resume=True, compress=compress))
    assert not any(await asyncio.gather(t_recv, t_send))
    assert dest_file.read_bytes() == data

    # --- Case 4: receiver has corrupted prefix -> sender overwrites full file ---
    corrupted = bytearray(data[:half])
    corrupted[10] ^= 0xFF  # flip a byte
    dest_file.write_bytes(corrupted)
    t_recv = asyncio.create_task(api_receive(server_url, code, encrypt=encrypt, out=str(recv_dir)))
    t_send = asyncio.create_task(api_send(server_url, code, [str(src_file)], encrypt=encrypt, resume=True, compress=compress))
    assert not any(await asyncio.gather(t_recv, t_send))
    assert dest_file.read_bytes() == data

    relay_task.cancel()