from __future__ import annotations

import asyncio
from typing import List, Optional

import typer
from p2p_copy import send as api_send, receive as api_receive
from p2p_copy.compressor import CompressMode
from p2p_copy_server import run_relay

app = typer.Typer(add_completion=False, help="p2p-copy — chunked file transfer over WSS (lean skeleton).")

@app.command()
def send(
    server: str = typer.Argument(..., help="Relay WSS URL, e.g. wss://relay.example"),
    code: str = typer.Argument(..., help="Shared passphrase/code"),
    files: List[str] = typer.Argument(..., help="Files to send"),
    encrypt: bool = typer.Option(False, help="Enable end-to-end encryption (future)"),
    compress: CompressMode = typer.Option(CompressMode.auto, help="Compression mode"),
    resume: bool = typer.Option(True, help="Attempt to resume interrupted transfers"),
):
    raise SystemExit(asyncio.run(api_send(
        files=files, code=code, server=server, encrypt=encrypt,
        compress=compress, resume=resume,
    )))

@app.command()
def receive(
    server: str = typer.Argument(..., help="Relay WSS URL, e.g. wss://relay.example"),
    code: str = typer.Argument(..., help="Shared passphrase/code"),
    resume: bool = typer.Option(True, help="Attempt to resume interrupted transfers"),
    out: Optional[str] = typer.Option(None, help="Output directory"),
):
    raise SystemExit(asyncio.run(api_receive(
        code=code, server=server, resume=resume, out=out,
    )))

@app.command("run-relay-server")
def run_relay_server(
        server_host: str = typer.Argument(..., help="Host, e. g. localhost"),
        server_port: int = typer.Argument(..., help="Port"),
        tls: bool = typer.Option(True, "--tls/--no-tls", help="use TLS to upgrade WS to WSS"),
        certfile: Optional[str] = typer.Option(None, help="Path to certfile (bei --tls)"),
        keyfile: Optional[str] = typer.Option(None, help="Path to Key (bei --tls)"),
):
    """
    starts the relay server
    """
    try:
        asyncio.run(run_relay(
            host=server_host,
            port=server_port,
            use_tls=tls,
            certfile=certfile,
            keyfile=keyfile,
        ))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    app()
