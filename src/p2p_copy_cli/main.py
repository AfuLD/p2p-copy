from __future__ import annotations

import asyncio
from typing import List, Optional

import typer
from p2p_copy import send as api_send, receive as api_receive
from p2p_copy.compressor import CompressMode

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

if __name__ == "__main__":
    app()
