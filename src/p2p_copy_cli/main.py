from __future__ import annotations

import asyncio
from typing import List, Optional

import typer
from p2p_copy import send as api_send, receive as api_receive
from p2p_copy.compressor import CompressMode
from p2p_copy_server import run_relay

app = typer.Typer(add_completion=False, help="p2p-copy — chunked file transfer over WSS.")

@app.command()
def send(
    server: str = typer.Argument(..., help="Relay WS(S) URL, e.g. wss://relay.example or ws://localhost:8765"),
    code: str = typer.Argument(..., help="Shared passphrase/code"),
    files: List[str] = typer.Argument(..., help="Files and/or directories to send"),
    encrypt: bool = typer.Option(False, help="Enable end-to-end encryption (future)"),
    compress: CompressMode = typer.Option(CompressMode.auto, help="Compression mode"),
    resume: bool = typer.Option(True, help="Attempt to resume interrupted transfers"),
):
    """Send one or more files/directories."""
    raise SystemExit(asyncio.run(api_send(
        files=files, code=code, server=server, encrypt=encrypt,
        compress=compress, resume=resume,
    )))

@app.command()
def receive(
    server: str = typer.Argument(..., help="Relay WS(S) URL, e.g. wss://relay.example or ws://localhost:8765"),
    code: str = typer.Argument(..., help="Shared passphrase/code"),
    resume: bool = typer.Option(True, help="Attempt to resume interrupted transfers"),
    out: Optional[str] = typer.Option(".", "--out", "-o", help="Output directory"),
):
    """Receive files into the target directory (default: .)."""
    raise SystemExit(asyncio.run(api_receive(
        code=code, server=server, resume=resume, out=out,
    )))

@app.command("run-relay-server")
def run_relay_server(
    server_host: str = typer.Argument("0.0.0.0", help="Host to bind"),
    server_port: int = typer.Argument(8765, help="Port to bind"),
    tls: bool = typer.Option(True, "--tls/--no-tls", help="Enable TLS (default: on)"),
    certfile: Optional[str] = typer.Option(None, help="TLS cert file (PEM)"),
    keyfile: Optional[str] = typer.Option(None, help="TLS key file (PEM)"),
):
    """Run the relay server (glue-only)."""
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
