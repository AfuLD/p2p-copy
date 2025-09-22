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


def _free_port() -> int:
    """Return a free TCP port for local WS tests."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

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

def test_transfer_timings_for_compression_modes_encrypted(tmp_path, capsys):
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