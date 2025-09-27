from __future__ import annotations

import asyncio
import json
import ssl
from typing import Dict, Tuple, Optional

from websockets.asyncio.server import serve, ServerConnection

from p2p_copy.protocol import READY

WAITING: Dict[str, Tuple[str, ServerConnection]] = {}  # code_hash -> (role, ws)
LOCK = asyncio.Lock()


def use_production_logger():
    """
    Configure logging for production use, suppressing tracebacks for handshake errors.
    """

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


async def _pipe(a: ServerConnection, b: ServerConnection) -> None:
    """
    Pipe data bidirectionally between two WebSocket connections until one closes.
    """

    try:
        async for frame in a:
            await b.send(frame)
    except Exception:
        pass
    finally:
        try:
            await b.close()
        except Exception:
            pass


async def _handle(ws: ServerConnection) -> None:
    """
    Handle a single WebSocket connection: validate hello, pair with peer, and pipe data.
    """

    # 1) expect hello (text)
    try:
        raw = await ws.recv()
    except Exception:
        return
    if not isinstance(raw, str):
        await ws.close(code=1002, reason="First frame must be hello text")
        return
    try:
        hello = json.loads(raw)
    except Exception:
        await ws.close(code=1002, reason="Bad hello json")
        return
    if hello.get("type") != "hello":
        await ws.close(code=1002, reason="First frame must be hello")
        return
    code_hash = hello.get("code_hash_hex")
    role = hello.get("role")
    if not code_hash or role not in {"sender", "receiver"}:
        await ws.close(code=1002, reason="Bad hello")
        return

    # 2) Pair by code_hash (exactly one sender + one receiver)
    peer: Optional[ServerConnection] = None
    async with LOCK:
        if code_hash in WAITING:
            other_role, peer = WAITING.pop(code_hash)
            if other_role == role:
                # two senders or two receivers — reject both
                await peer.close(code=1013, reason="Duplicate role for code")
                await ws.close(code=1013, reason="Duplicate role for code")
                return
        else:
            WAITING[code_hash] = (role, ws)

    if peer is None:
        # wait until paired; then this handler exits when ws closes
        try:
            await ws.wait_closed()
        finally:
            async with LOCK:
                if WAITING.get(code_hash, (None, None))[1] is ws:
                    WAITING.pop(code_hash, None)
        return

    # 3) Start bi-directional piping
    t1 = asyncio.create_task(_pipe(ws, peer))
    t2 = asyncio.create_task(_pipe(peer, ws))

    # 4) Inform sender that pipe is ready
    await (ws if role == "sender" else peer).send(READY)

    # wait for one side to finish
    done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)

    # give the slower side up to 1 second to finish
    sleep_task = asyncio.create_task(asyncio.sleep(1.0))
    done2, pending2 = await asyncio.wait(pending | {sleep_task}, return_when=asyncio.FIRST_COMPLETED)

    # cancel whatever is still pending (excluding the sleep_task)
    for t in pending2:
        if t is not sleep_task:
            t.cancel()


async def run_relay(host: str, port: int,
                    use_tls: bool = True,
                    certfile: Optional[str] = None,
                    keyfile: Optional[str] = None) -> None:
    """
    Run the WebSocket relay server, optionally with TLS.

    Parameters
    ----------
    host : str
        Host to bind to.
    port : int
        Port to bind to.
    use_tls : bool, optional
        Whether to use TLS. Default is True.
    certfile : str, optional
        Path to TLS certificate file.
    keyfile : str, optional
        Path to TLS key file.

    Raises
    ------
    RuntimeError
        If TLS is requested but certfile or keyfile is missing.
    """
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

    async with serve(_handle, host, port, max_size=2**21, ssl=ssl_ctx, compression=None):
        await asyncio.Future()  # run forever
