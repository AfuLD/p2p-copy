from __future__ import annotations

import asyncio
import json
import ssl
from typing import Dict, Tuple, Optional

from websockets.asyncio.server import serve, ServerConnection

WAITING: Dict[str, Tuple[str, ServerConnection]] = {}  # code_hash -> (role, ws)
LOCK = asyncio.Lock()

async def _handle(ws: ServerConnection) -> None:
    # 1) hello (Text) erwarten
    try:
        raw = await ws.recv()
        if isinstance(raw, bytes):
            await ws.close(code=1002, reason="Expected hello text frame")
            return
        hello = json.loads(raw)
    except Exception:
        await ws.close(code=1002, reason="Invalid hello")
        return

    if hello.get("type") != "hello":
        await ws.close(code=1002, reason="First frame must be hello")
        return
    code_hash = hello.get("code_hash_hex")
    role = hello.get("role")
    if not code_hash or role not in {"sender", "receiver"}:
        await ws.close(code=1002, reason="Bad hello")
        return

    # 2) Pairing nach code_hash (genau ein Sender + ein Empfänger)
    peer: Optional[ServerConnection] = None
    async with LOCK:
        if code_hash in WAITING:
            other_role, other_ws = WAITING.pop(code_hash)
            if other_role == role:
                await ws.close(code=1013, reason="Peer with same role already waiting")
                WAITING[code_hash] = (other_role, other_ws)  # alten Wartenden behalten
                return
            peer = other_ws
        else:
            WAITING[code_hash] = (role, ws)

    if peer is None:
        try:
            await ws.wait_closed()
        finally:
            async with LOCK:
                if WAITING.get(code_hash, (None, None))[1] is ws:
                    WAITING.pop(code_hash, None)
        return

    # 3) Bidirektionales Piping
    async def pipe(a: ServerConnection, b: ServerConnection):
        try:
            async for msg in a:
                await b.send(msg)
        except Exception:
            pass
        finally:
            await b.close()

    await asyncio.gather(pipe(ws, peer), pipe(peer, ws))

async def run_relay(
        host: str,
        port: int,
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
        await asyncio.Future()  # läuft dauerhaft
