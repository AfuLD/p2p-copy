"""
Simple relay for Phase 2 (modern websockets asyncio API).

- Clients connect via WS(S) and first send a JSON 'hello' message:
  {"type":"hello","code_hash_hex": "...","role":"sender"|"receiver","protocol_version":1}
- The relay pairs connections by code_hash_hex when both roles are present.
- After pairing, it pipes frames (text+binary) bidirectionally until one side closes.
"""

import argparse
import asyncio
import json
from typing import Dict, Tuple, Optional

from websockets.asyncio.server import serve, ServerConnection

WAITING: Dict[str, Tuple[str, ServerConnection]] = {}  # code_hash -> (role, ws)
LOCK = asyncio.Lock()

async def handle(ws: ServerConnection):
    # 1) Expect a hello JSON text frame
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

    # 2) Pair by code_hash (one sender + one receiver)
    peer: Optional[ServerConnection] = None
    async with LOCK:
        if code_hash in WAITING:
            other_role, other_ws = WAITING.pop(code_hash)
            if other_role == role:
                # Same role waiting — keep original, reject second
                await ws.close(code=1013, reason="Peer with same role already waiting")
                WAITING[code_hash] = (other_role, other_ws)
                return
            peer = other_ws
        else:
            WAITING[code_hash] = (role, ws)

    if peer is None:
        # Wait (or cleanup if closed)
        try:
            await ws.wait_closed()
        finally:
            async with LOCK:
                if WAITING.get(code_hash, (None, None))[1] is ws:
                    WAITING.pop(code_hash, None)
        return

    # 3) Pipe both directions
    async def pipe(a: ServerConnection, b: ServerConnection):
        try:
            async for msg in a:
                await b.send(msg)
        except Exception:
            pass
        finally:
            await b.close()

    await asyncio.gather(pipe(ws, peer), pipe(peer, ws))

async def main(host: str, port: int):
    print(f"Relay listening on ws://{host}:{port}")
    async with serve(handle, host, port, max_size=None):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass
