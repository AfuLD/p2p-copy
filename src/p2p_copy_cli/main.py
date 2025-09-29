from __future__ import annotations

import asyncio
from typing import List, Optional

import typer
from p2p_copy import send as api_send, receive as api_receive
from p2p_copy import CompressMode
from p2p_copy_server import run_relay

import sys

if hasattr(sys.stdout, "reconfigure"):  # on Python >= 3.7
    sys.stdout.reconfigure(line_buffering=True)

app = typer.Typer(add_completion=False, help="p2p-copy — chunked file transfer over WSS.")


@app.command(help="""
Send one or more files or directories to a paired receiver via the relay server.

This command connects to the specified WebSocket relay server, authenticates using
the shared passphrase (hashed for pairing), and streams the provided files/directories
in chunks to the receiver. Supports directories by recursively including all files
in alphabetical order. Optional end-to-end encryption (AES-GCM) and compression
(Zstandard, auto-detected per file) can be enabled. If resume is enabled, it
coordinates with the receiver to skip complete files or append to partial ones
based on chained checksum verification.


Examples

Send a single file:

$ p2p-copy send wss://relay.example.com:443 mycode /path/to/file.txt

Send a directory with compression and resume:

$ p2p-copy send wss://relay.example.com:443 mycode /path/to/dir --compress on --resume

Send multiple specified files with encryption:

$ p2p-copy send ws://localhost:8765 mycode *.txt --encrypt
""")
def send(
        server: str = typer.Argument(..., help="Relay WS(S) URL, e.g. wss://relay.example:443 or ws://localhost:8765"),
        code: str = typer.Argument(..., help="Shared passphrase/code"),
        files: List[str] = typer.Argument(..., help="Files and/or directories to send"),
        encrypt: bool = typer.Option(False, help="Enable end-to-end encryption"),
        compress: CompressMode = typer.Option(CompressMode.auto, help="Enable Compression"),
        resume: bool = typer.Option(False,
                                    help="resume previous copy progress, skips existing and completes partial files"),
):
    """
    Send one or more files or directories to a paired receiver via the relay server.

    Parameters
    ----------
    server : str
        The WebSocket server URL (ws:// or wss://).
    code : str
        The shared passphrase/code for pairing.
    files : List[str]
        List of files and/or directories to send.
    encrypt : bool, optional
        Enable end-to-end encryption. Default is False.
    compress : CompressMode, optional
        Compression mode. Default is 'auto'.
    resume : bool, optional
        Enable resume of partial transfers. Default is False.

    Returns
    -------
    int
        Exit code: 0 on success, non-zero on error.

    Notes
    -----
    - Supports resuming by comparing checksums of partial files.
    - Uses chunked streaming for large files.
    """
    raise SystemExit(asyncio.run(api_send(
        files=files, code=code, server=server, encrypt=encrypt,
        compress=compress, resume=resume,
    )))


@app.command(help="""
Receive files from a paired sender via the relay server and write to the output directory.

This command connects to the relay server, pairs using the shared passphrase hash,
and receives a manifest of incoming files/directories. Files are written to the
output directory, preserving relative paths from the manifest. Supports optional
end-to-end decryption (matching sender's encryption) and decompression. If the
sender requests resume, this receiver reports existing file states (via checksums)
to enable skipping or appending.

Examples

Receive to current directory:

$ p2p-copy receive wss://relay.example.com:443 mycode

Receive to a specific directory with encryption:

$ p2p-copy receive ws://localhost:8765 mycode --out /tmp/downloads --encrypt
""")
def receive(
        server: str = typer.Argument(..., help="Relay WS(S) URL, e.g. wss://relay.example:443 or ws://localhost:8765"),
        code: str = typer.Argument(..., help="Shared passphrase/code"),
        encrypt: bool = typer.Option(False, help="Enable end-to-end encryption"),
        out: Optional[str] = typer.Option(".", "--out", help="Output directory"),
):
    """
    Receive files from a sender via the relay server.

    Parameters
    ----------
    server : str
        The WebSocket server URL (ws:// or wss://).
    code : str
        The shared passphrase/code for pairing.
    encrypt : bool, optional
        Enable end-to-end encryption. Default is False.
    out : str, optional
        Output directory. Default is current directory.

    Returns
    -------
    int
        Exit code: 0 on success, non-zero on error.

    Notes
    -----
    - Supports resume if sender requests it.
    - Writes files to the output directory, preserving relative paths.
    """
    raise SystemExit(asyncio.run(api_receive(
        code=code, server=server, encrypt=encrypt, out=out,
    )))


@app.command("run-relay-server", help="""
Run the WebSocket relay server for pairing and forwarding client connections.

This command starts a relay server that listens on the specified host/interface and port,
optionally secured with TLS (recommended for production). The server pairs
sender and receiver clients based on matching passphrase hashes, then forwards
bidirectional data streams without storing content. It handles exactly one
sender and one receiver per code hash, rejecting duplicates. Use for secure,
firewall-friendly (port 443) P2P transfers.

Examples

Run on localhost without TLS (development):

$ p2p-copy run-relay-server localhost 8765 --no-tls

Run with TLS on a public host:

$ p2p-copy run-relay-server 0.0.0.0 443 --tls --certfile cert.pem --keyfile key.pem
""")
def run_relay_server(
        server_host: str = typer.Argument(..., help="Host/Interface to bind"),
        server_port: int = typer.Argument(..., help="Port to bind"),
        tls: bool = typer.Option(True, "--tls/--no-tls", help="Enable WSS/TLS"),
        certfile: Optional[str] = typer.Option(None, help="TLS cert file (PEM)"),
        keyfile: Optional[str] = typer.Option(None, help="TLS key file (PEM)"),
):
    """
    Run the relay server.

    Parameters
    ----------
    server_host : str
        Host/Interface to bind to.
    server_port : int
        Port to bind to.
    tls : bool, optional
        Enable TLS. Default is True.
    certfile : str, optional
        Path to TLS certificate file (PEM).
    keyfile : str, optional
        Path to TLS key file (PEM).

    Returns
    -------
    None
        Runs indefinitely until interrupted (e.g., Ctrl+C).

    Notes
    -----
    - Requires certfile and keyfile if TLS is enabled.
    - Configures production logging if host is not localhost.
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
