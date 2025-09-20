from __future__ import annotations

import asyncio
import hashlib
import socket
import subprocess
import time
from contextlib import closing
from pathlib import Path

import pytest

from p2p_copy import send as api_send, receive as api_receive
from p2p_copy.protocol import Manifest, ManifestEntry, loads
from p2p_copy_server.relay import run_relay


# ---------- helpers ----------

def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _mk_files(base: Path, layout: dict[str, bytes]) -> None:
    for rel, content in layout.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- protocol-level/unit checks (serialization stays stable) ----------

def test_phase3_manifest_serialization_roundtrip(tmp_path: Path):
    entries = [
        ManifestEntry(path="dir/a.txt", size=7),
        ManifestEntry(path="b.bin", size=2),
    ]
    m = Manifest(type="manifest", entries=entries)
    s = m.to_json()
    obj = loads(s)
    assert obj["type"] == "manifest"
    assert len(obj["entries"]) == 2
    # ensure stable keys/values for forwards/backwards compatibility
    assert obj["entries"][0]["path"] == "dir/a.txt"
    assert isinstance(obj["entries"][0]["size"], int)

# ---------- end-to-end over API (multi-file + integrity) ----------

def test_phase3_api_multi_file_ws(tmp_path: Path):
    asyncio.run(async_test_phase3_api_multi_file_ws(tmp_path))


async def async_test_phase3_api_multi_file_ws(tmp_path: Path):
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    code = "phase3-demo"

    # input tree
    src = tmp_path / "src"
    _mk_files(
        src,
        {
            "dir1/a.txt": b"hello a",
            "dir1/b.bin": b"bbb",
            "c.txt": b"phase3 test",
        },
    )

    out = tmp_path / "out"

    # start relay without TLS for local test speed/stability
    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    try:
        # give the server a moment to start listening (works across IPv4/IPv6)
        await asyncio.sleep(0.1)

        # run receiver first to avoid race
        recv_task = asyncio.create_task(
            api_receive(server=server_url, code=code, encrypt=False, out=str(out))
        )
        await asyncio.sleep(0.05)

        send_rc = await api_send(server=server_url, code=code, files=[str(src)])
        try:
            recv_rc = await asyncio.wait_for(recv_task, timeout=10.0)
        except asyncio.TimeoutError:
            recv_task.cancel()
            raise

        assert send_rc == 0
        assert recv_rc == 0

        # verify files arrived with same bytes (integrity)
        assert (out / "src/dir1/a.txt").read_bytes() == (src / "dir1/a.txt").read_bytes()
        assert (out / "src/dir1/b.bin").read_bytes() == (src / "dir1/b.bin").read_bytes()
        assert (out / "src/c.txt").read_bytes() == (src / "c.txt").read_bytes()

        # and hashes match as additional safety
        for rel in ("dir1/a.txt", "dir1/b.bin", "c.txt"):
            assert _sha256(out / "src" / rel) == _sha256(src / rel)
    finally:
        relay_task.cancel()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(relay_task, timeout=0.1)


# ---------- end-to-end via CLI (multi-file) ----------

def test_phase3_cli_multi_file_ws(tmp_path: Path):
    host = "localhost"
    port = _free_port()
    code = "phase3-cli"

    src = tmp_path / "src"
    out = tmp_path / "out"
    _mk_files(
        src,
        {"dir/sub/file1.txt": b"cli-one",
         "file2.txt": b"cli-two",
         },
    )

    # 1) start relay as subprocess using installed console_script (like existing tests)
    relay_proc = subprocess.Popen(
        ["p2p-copy", "run-relay-server", host, str(port), "--no-tls"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        # wait a bit until relay is accepting connections (works for v4/v6)
        time.sleep(0.1)

        # 2) start receiver (CLI)
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

        # 3) run sender (CLI)
        send_run = subprocess.run(
            [
                "p2p-copy",
                "send",
                f"ws://{host}:{port}",
                code,
                str(src),
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert send_run.returncode == 0, f"send CLI failed: {send_run.stdout}{send_run.stderr}"

        # 4) receiver should exit cleanly
        recv_rc = recv_proc.wait(timeout=5)
        if recv_rc != 0:
            out_log = recv_proc.stdout.read() if recv_proc.stdout else ""
            pytest.fail(f"receive CLI failed (rc={recv_rc}):{out_log}")

        # 5) verify
        assert (out / "src/dir/sub/file1.txt").read_bytes() == b"cli-one"
        assert (out / "src/file2.txt").read_bytes() == b"cli-two"

    finally:
        # cleanup relay
        relay_proc.terminate()
        try:
            relay_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            relay_proc.kill()
