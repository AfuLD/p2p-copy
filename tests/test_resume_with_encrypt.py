# tests/test_resume.py

import asyncio
import os
import random
import socket
from pathlib import Path
from contextlib import closing

import pytest

from p2p_copy import send as api_send, receive as api_receive, CompressMode
from p2p_copy_server.relay import run_relay


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _make_bytes(n: int) -> bytes:
    rnd = random.Random(42)
    return bytes(rnd.getrandbits(8) for _ in range(n))


@pytest.mark.parametrize("encrypt", [False, True])
@pytest.mark.parametrize("compress", [CompressMode.off, CompressMode.on])
def test_resume(tmp_path: Path, encrypt: bool, compress: CompressMode):
    asyncio.run(resume(tmp_path, encrypt, compress))

async def resume(tmp_path: Path, encrypt: bool, compress: CompressMode):
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
    data = _make_bytes(2200_000)  # ~200 KB
    src_file.write_bytes(data)

    # Receiver dir
    recv_dir = tmp_path / "recv"
    recv_dir.mkdir()

    # --- Case 1: no file present yet ---
    t_recv = asyncio.create_task(api_receive(server_url, code, encrypt=encrypt, out=str(recv_dir)))
    t_send = asyncio.create_task(api_send(server_url, code, [str(src_file)], encrypt=encrypt, resume=True, compress=compress))
    await asyncio.gather(t_recv, t_send)

    dest_file = recv_dir / "src.bin"
    assert dest_file.read_bytes() == data

    # --- Case 2: receiver already has full file -> sender skips ---
    t_recv = asyncio.create_task(api_receive(server_url, code, encrypt=encrypt, out=str(recv_dir)))
    t_send = asyncio.create_task(api_send(server_url, code, [str(src_file)], encrypt=encrypt, resume=True, compress=compress))
    await asyncio.gather(t_recv, t_send)
    # File should be unchanged
    assert dest_file.read_bytes() == data

    # --- Case 3: receiver has partial file -> sender appends remainder ---
    half = len(data) // 2
    dest_file.write_bytes(data[:half])  # truncate to half
    t_recv = asyncio.create_task(api_receive(server_url, code, encrypt=encrypt, out=str(recv_dir)))
    t_send = asyncio.create_task(api_send(server_url, code, [str(src_file)], encrypt=encrypt, resume=True, compress=compress))
    await asyncio.gather(t_recv, t_send)
    assert dest_file.read_bytes() == data

    # --- Case 4: receiver has corrupted prefix -> sender overwrites full file ---
    corrupted = bytearray(data[:half])
    corrupted[10] ^= 0xFF  # flip a byte
    dest_file.write_bytes(corrupted)
    t_recv = asyncio.create_task(api_receive(server_url, code, encrypt=encrypt, out=str(recv_dir)))
    t_send = asyncio.create_task(api_send(server_url, code, [str(src_file)], encrypt=encrypt, resume=True, compress=compress))
    await asyncio.gather(t_recv, t_send)
    assert dest_file.read_bytes() == data

    relay_task.cancel()

