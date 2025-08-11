from __future__ import annotations
import asyncio
from typing import List, Optional, Literal
import typer
from p2p_copy import send as api_send, receive as api_receive

app = typer.Typer(add_completion=False, help="p2p-copy — chunked file transfer over WSS (lean skeleton).")

@app.command()
def send(
    server: str = typer.Option(..., help="Relay WSS URL, e.g. wss://relay.example"),
    code: str = typer.Option(..., help="Shared passphrase/code"),
    files: List[str] = typer.Argument(..., help="Files to send"),
    encrypt: bool = typer.Option(False, help="Enable end-to-end encryption (future)"),
    compress: Literal["auto", "on", "off"] = typer.Option("auto", help="Compression mode"),
    chunk_size: int = typer.Option(1 << 20, help="Chunk size in bytes (default: 1 MiB)"),
    resume: bool = typer.Option(True, help="Attempt to resume interrupted transfers"),
):
    raise SystemExit(asyncio.run(api_send(
        files=files, code=code, server=server, encrypt=encrypt,
        compress=compress, chunk_size=chunk_size, resume=resume,
    )))

@app.command()
def receive(
    server: str = typer.Option(..., help="Relay WSS URL, e.g. wss://relay.example"),
    code: str = typer.Option(..., help="Shared passphrase/code"),
    out: Optional[str] = typer.Option(None, help="Output directory"),
    encrypt: bool = typer.Option(False, help="Enable end-to-end encryption (future)"),
    resume: bool = typer.Option(True, help="Attempt to resume interrupted transfers"),
):
    raise SystemExit(asyncio.run(api_receive(
        code=code, server=server, encrypt=encrypt, resume=resume, out=out,
    )))

if __name__ == "__main__":
    app()
