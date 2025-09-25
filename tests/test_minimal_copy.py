from __future__ import annotations

import asyncio
import socket
import subprocess
import time
from contextlib import closing
from pathlib import Path

from p2p_copy import send as api_send, receive as api_receive
from p2p_copy_server.relay import run_relay


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def test_api_wont_accept_unintended_files(tmp_path: Path):
    asyncio.run(async_api_wont_accept_file_string(tmp_path))

async def async_api_wont_accept_file_string(tmp_path: Path):
    """Einfacher End-to-End-Transfer über WS (kein TLS), eine Datei."""
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    code = "demo"

    # Relay im Hintergrund starten (kein TLS für lokale Tests)
    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    # Warten bis der Server lauscht
    await asyncio.sleep(0.1)

    # Dateien vorbereiten
    src = tmp_path / "sample.txt"
    src.write_text("hello phase2", encoding="utf-8")
    out_dir = tmp_path / "downloads"

    # Receiver startet und wartet; Sender schickt danach
    recv_task = asyncio.create_task(
        api_receive(code=code, server=server_url, out=str(out_dir))
    )
    await asyncio.sleep(0.1)  # Receiver bereit werden lassen

    try:
        # noinspection PyTypeChecker
        send_rc = await asyncio.wait_for(
            asyncio.create_task(api_send(files=str(src), code=code, server=server_url)),
            timeout=2)
    except asyncio.TimeoutError:
        send_rc = 999
    try:
        recv_rc = await asyncio.wait_for(recv_task, timeout=0.2)
    except asyncio.TimeoutError:
        recv_rc = 999

    assert send_rc != 0 and recv_rc != 0, "files as non-list should not be allowed"

    await asyncio.sleep(0.1)
    recv_task = asyncio.create_task(
        api_receive(code=code, server=server_url, out=str(out_dir))
    )
    await asyncio.sleep(0.1)  # Receiver bereit werden lassen

    try:
        send_rc = await asyncio.wait_for(
            asyncio.create_task(api_send(files=[], code=code, server=server_url)),
            timeout=2)
    except asyncio.TimeoutError:
        send_rc = 999
    try:
        recv_rc = await asyncio.wait_for(recv_task, timeout=0.2)
    except asyncio.TimeoutError:
        recv_rc = 999

    assert send_rc != 0 and recv_rc != 0, "files as empty list should not be allowed"

    await asyncio.sleep(0.1)
    recv_task = asyncio.create_task(
        api_receive(code=code, server=server_url, out=str(out_dir))
    )
    await asyncio.sleep(0.1)  # Receiver bereit werden lassen

    try:
        send_rc = await asyncio.wait_for(
            asyncio.create_task(api_send(files=["xx","t"], code=code, server=server_url)),
            timeout=2)
    except asyncio.TimeoutError:
        send_rc = 999
    try:
        recv_rc = await asyncio.wait_for(recv_task, timeout=0.2)
    except asyncio.TimeoutError:
        recv_rc = 999

    assert send_rc != 0 and recv_rc != 0, "implausibly short files should not be allowed"

    # Aufräumen: Relay stoppen
    relay_task.cancel()

    # Asserts
    assert send_rc != 0 and recv_rc != 0
    dest = out_dir / "sample.txt"
    assert not dest.exists(), "Zieldatei fehlt nicht"

def test_e2e_single_file_ws(tmp_path: Path):
        asyncio.run(async_test_e2e_single_file_ws(tmp_path))

async def async_test_e2e_single_file_ws(tmp_path: Path):
    """Einfacher End-to-End-Transfer über WS (kein TLS), eine Datei."""
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"
    code = "demo"

    # Relay im Hintergrund starten (kein TLS für lokale Tests)
    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    # Warten bis der Server lauscht
    await asyncio.sleep(0.1)

    # Dateien vorbereiten
    src = tmp_path / "sample.txt"
    src.write_text("hello phase2", encoding="utf-8")
    out_dir = tmp_path / "downloads"

    # Receiver startet und wartet; Sender schickt danach
    recv_task = asyncio.create_task(
        api_receive(code=code, server=server_url, out=str(out_dir))
    )
    await asyncio.sleep(0.05)  # Receiver bereit werden lassen
    send_rc = await api_send(files=[str(src)], code=code, server=server_url)

    recv_rc = await asyncio.wait_for(recv_task, timeout=5.0)

    # Aufräumen: Relay stoppen
    relay_task.cancel()

    # Asserts
    assert send_rc == 0 and recv_rc == 0
    dest = out_dir / "sample.txt"
    assert dest.exists(), "Zieldatei fehlt"
    assert dest.read_text(encoding="utf-8") == "hello phase2"

def test_pairing_isolated_by_code(tmp_path: Path):
    asyncio.run(async_test_pairing_isolated_by_code(tmp_path))

async def async_test_pairing_isolated_by_code(tmp_path: Path):
    """Zwei parallele Paare mit unterschiedlichen Codes dürfen sich nicht vermischen."""
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"

    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    await asyncio.sleep(0.1)

    # Daten A
    code_a = "codeA"
    src_a = tmp_path / "a.txt"
    src_a.write_text("AAA", encoding="utf-8")
    out_a = tmp_path / "outA"

    # Daten B
    code_b = "codeB"
    src_b = tmp_path / "b.txt"
    src_b.write_text("BBB", encoding="utf-8")
    out_b = tmp_path / "outB"

    recv_a = asyncio.create_task(api_receive(code=code_a, server=server_url, out=str(out_a)))
    recv_b = asyncio.create_task(api_receive(code=code_b, server=server_url, out=str(out_b)))

    await asyncio.sleep(0.05)
    send_a = asyncio.create_task(api_send(files=[str(src_a)], code=code_a, server=server_url))
    send_b = asyncio.create_task(api_send(files=[str(src_b)], code=code_b, server=server_url))

    send_rc_a, send_rc_b = await asyncio.gather(send_a, send_b)
    recv_rc_a, recv_rc_b = await asyncio.gather(recv_a, recv_b)

    relay_task.cancel()

    assert send_rc_a == 0 and send_rc_b == 0
    assert recv_rc_a == 0 and recv_rc_b == 0
    assert (tmp_path / "outA" / "a.txt").read_text(encoding="utf-8") == "AAA"
    assert (tmp_path / "outB" / "b.txt").read_text(encoding="utf-8") == "BBB"

def test_reject_same_role_sender(tmp_path: Path):
    asyncio.run(async_test_reject_same_role_sender(tmp_path))

async def async_test_reject_same_role_sender(tmp_path: Path):
    """Zwei Sender mit demselben Code: der zweite wird mit 1013 abgewiesen."""
    host = "localhost"
    port = _free_port()
    server_url = f"ws://{host}:{port}"

    relay_task = asyncio.create_task(run_relay(host=host, port=port, use_tls=False))
    await asyncio.sleep(0.1)

    # Niedrig-Level: websockets-Client direkt, um die Hello-Nachricht zu senden
    from websockets.asyncio.client import connect
    from p2p_copy.protocol import  dumps

    code = "same-role"
    hello_sender = dumps({
        "type": "hello",
        "code_hash_hex": code,
        "role": "sender",
        "protocol_version": 1
    })

    async with connect(server_url) as ws1:
        await ws1.send(hello_sender)
        async with connect(server_url) as ws2:
            await ws2.send(hello_sender)
            # Der zweite sollte bald geschlossen werden
            await asyncio.wait_for(ws2.wait_closed(), timeout=2.0)
            # 1013 laut Relay-Implementierung
            assert ws2.close_code == 1013

        # Ersten sauber schließen
        await ws1.close()

    relay_task.cancel()


def test_cli_end_to_end_ws(tmp_path: Path):
    """
    End-to-End über die CLI:
      - Relay via CLI (Default TLS=True, hier explizit --no-tls)
      - receive via CLI
      - send via CLI
    """
    host = "localhost"
    port = _free_port()
    code = "cli-demo"

    # Relay starten (blockiert), daher in Popen + --no-tls
    relay_proc = subprocess.Popen(
        ["p2p-copy", "run-relay-server", host, str(port), "--no-tls"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Warten bis der Relay Server lauscht
    time.sleep(0.1)

    # Receiver starten (wartet)
    out_dir = tmp_path / "downloads"
    recv_proc = subprocess.Popen(
        ["p2p-copy", "receive", f"ws://{host}:{port}", code, "--out", str(out_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(0.1)

    # Sender starten
    src = tmp_path / "sample.txt"
    src.write_text("hello from cli", encoding="utf-8")
    src2 = tmp_path / "sample2.txt"
    src2.write_text("hello2 from cli", encoding="utf-8")

    send_proc = subprocess.run(
        ["p2p-copy", "send", f"ws://{host}:{port}", code, str(src), str(src2)],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert send_proc.returncode == 0, f"send CLI failed: {send_proc.stdout}\n{send_proc.stderr}"

    # Receiver sollte beendet sein
    recv_rc = recv_proc.wait(timeout=5)
    assert recv_rc == 0, f"receive CLI failed: {recv_proc.stdout and recv_proc.stdout.read()}"

    # Prüfen
    dest = out_dir / "sample.txt"
    assert dest.exists() and dest.read_text(encoding="utf-8") == "hello from cli"

    dest2 = out_dir / "sample2.txt"
    assert dest2.exists() and dest2.read_text(encoding="utf-8") == "hello2 from cli"

    # Aufräumen
    relay_proc.terminate()
    try:
        relay_proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        relay_proc.kill()
