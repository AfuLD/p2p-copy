# test_compression.py
from __future__ import annotations

import asyncio
import random
import socket
import subprocess
import time
from contextlib import closing
from pathlib import Path

import pytest

# API entry points
from p2p_copy import send as api_send, receive as api_receive
from p2p_copy.compressor import CompressMode


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

def _compressible_bytes(n: int) -> bytes:
    # long runs of the same few chars -> easy to compress
    return (b"AAAABBBBCCCCDDDDEEEE" * ((n // 20) + 1))[:n]

def _incompressible_bytes(n: int) -> bytes:
    # pseudo-random noise -> hard to compress
    rnd = random.Random(42)
    return bytes(rnd.getrandbits(8) for _ in range(n))

# ---------- unit-ish: WS "compression=None" is enforced ----------

@pytest.mark.parametrize("mode", [CompressMode.off, CompressMode.on, CompressMode.auto])
def test_api_compression_modes_end_to_end(tmp_path, mode):
    asyncio.run(async_test_api_compression_modes_end_to_end(tmp_path, mode))

async def async_test_api_compression_modes_end_to_end(tmp_path: Path, mode: CompressMode):
    # lazy import to avoid circulars if your test runner reorders things
    from p2p_copy_server.relay import run_relay

    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    code = f"compress-api-{mode.value}"

    src = tmp_path / "src"
    out = tmp_path / "out"

    # 2 files: one very compressible, one incompressible, plus a tiny file
    _mk_files(
        src,
        {
            "big/compressible.bin": _compressible_bytes(512_000),   # ~500 KiB
            "big/incompressible.bin": _incompressible_bytes(512_000),
            "tiny.txt": b"tiny",
        },
    )

    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    try:
        await asyncio.sleep(0.1)

        recv_task = asyncio.create_task(
            api_receive(server=server_url, code=code, encrypt=False, out=str(out))
        )
        await asyncio.sleep(0.05)

        # pass through the compression mode under test
        send_rc = await api_send(server=server_url, code=code, files=[str(src)], compress=mode)
        try:
            recv_rc = await asyncio.wait_for(recv_task, timeout=15.0)
        except asyncio.TimeoutError:
            recv_task.cancel()
            raise

        assert send_rc == 0
        assert recv_rc == 0

        # integrity checks (bytes must match regardless of compression mode)
        for rel in (
                "big/compressible.bin",
                "big/incompressible.bin",
                "tiny.txt",
        ):
            assert (out / "src" / rel).read_bytes() == (src / rel).read_bytes()

    finally:
        relay_task.cancel()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(relay_task, timeout=0.1)

# ---------- end-to-end CLI: off / on / auto ----------

@pytest.mark.parametrize("mode_flag", ["off", "on", "auto"])
def test_cli_compression_modes(tmp_path, mode_flag):
    """
    Smoke test your CLI for all three modes. Mirrors your phase-3 CLI test,
    but adds the --compress flag with off/on/auto.
    """
    host = "localhost"
    port = _free_port()
    code = f"compress-cli-{mode_flag}"

    src = tmp_path / "src"
    out = tmp_path / "out"
    _mk_files(
        src,
        {
            "dir/comp.txt": _compressible_bytes(64_000),
            "dir/incomp.bin": _incompressible_bytes(64_000),
        },
    )

    relay_proc = subprocess.Popen(
        ["p2p-copy", "run-relay-server", host, str(port), "--no-tls"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        time.sleep(0.1)

        recv_proc = subprocess.Popen(
            [
                "p2p-copy",
                "receive",
                f"ws://{host}:{port}",
                code,
                "--out",
                str(out),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        time.sleep(0.1)

        send_run = subprocess.run(
            [
                "p2p-copy",
                "send",
                f"ws://{host}:{port}",
                code,
                "--compress",
                mode_flag,
                str(src),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert send_run.returncode == 0, f"send CLI failed ({mode_flag}): {send_run.stdout}\n{send_run.stderr}"

        recv_rc = recv_proc.wait(timeout=10)
        if recv_rc != 0:
            out_log = recv_proc.stdout.read() if recv_proc.stdout else ""
            pytest.fail(f"receive CLI failed (rc={recv_rc}, mode={mode_flag}):\n{out_log}")

        # integrity
        assert (out / "src/dir/comp.txt").read_bytes() == (src / "dir/comp.txt").read_bytes()
        assert (out / "src/dir/incomp.bin").read_bytes() == (src / "dir/incomp.bin").read_bytes()

    finally:
        relay_proc.terminate()
        try:
            relay_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            relay_proc.kill()

# ---------- behavioral smoke: auto should *tend* to compress only when worth it ----------

def test_auto_mode_prefers_compressible(tmp_path):
    """
    This is a behavior check (not protocol introspection): we do two separate runs.
    While we can't directly assert the chosen mode without peeking into messages,
    we can at least ensure both runs succeed under auto, covering both code paths.
    """
    asyncio.run(_two_runs_under_auto(tmp_path))

async def _two_runs_under_auto(tmp_path: Path):
    from p2p_copy_server.relay import run_relay

    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))

    try:
        for label, payload_fn in [
            ("auto-compressible", _compressible_bytes),
            ("auto-incompressible", _incompressible_bytes),
        ]:

            code = f"{label}-code"
            src = tmp_path / label / "src"
            out = tmp_path / label / "out"
            _mk_files(src, {"file.bin": payload_fn(400_000)})

            await asyncio.sleep(0.1)
            recv_task = asyncio.create_task(api_receive(server=server_url, code=code, encrypt=False, out=str(out)))
            await asyncio.sleep(0.05)
            send_rc = await api_send(server=server_url, code=code, files=[str(src)], compress=CompressMode.auto)
            recv_rc = await asyncio.wait_for(recv_task, timeout=15.0)

            assert send_rc == 0
            assert recv_rc == 0
            assert (out / "src/file.bin").read_bytes() == (src / "file.bin").read_bytes()

    finally:
        relay_task.cancel()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(relay_task, timeout=0.1)


def test_transfer_timings_for_compression_modes(tmp_path):
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
                await asyncio.sleep(0.01)
                elapsed = await _time_one_transfer(payload, mode, tmp_path, f"{label}", server_url)
                results[label][mode.value] = elapsed

        relay_task.cancel()
        return results

    results = asyncio.run(run_all())

    # Pretty-print timings into test output for debugging
    print("\nTiming results (seconds):")
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
    assert comp_on <= comp_off * 0.75, f"Expected 'on' to be faster on compressible data (on={comp_on:.3f}s, off={comp_off:.3f}s)"
    assert comp_on * 0.9 - 0.01 <= comp_auto <=  comp_off * 0.75, \
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

    recv_task = asyncio.create_task(api_receive(server=server_url, code=code, encrypt=False, out=str(out)))
    await asyncio.sleep(0.1)  # ensure receiver is listening

    t0 = time.monotonic()
    send_rc = await api_send(server=server_url, code=code, files=[str(src)], compress=mode, encrypt=False)
    recv_rc = await asyncio.wait_for(recv_task, timeout=2.0)
    elapsed = time.monotonic() - t0

    assert send_rc == 0
    assert recv_rc == 0
    assert (out / f"src-{label}-{mode.value}" / "file.bin").read_bytes() == payload
    return elapsed
