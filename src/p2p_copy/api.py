from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Optional

from p2p_copy.compressor import CompressMode
from websockets.asyncio.client import connect

from .chunker import read_in_chunks
from .io_utils import iter_files, ensure_dir
from .protocol import Hello, Manifest, ManifestEntry, code_to_hash_hex, loads, EOF


async def send(
        *, server: str, code: str, files: Iterable[str],
        encrypt: bool = False,                       # reserved
        compress: CompressMode = CompressMode.auto,  # reserved
        resume: bool = True,                         # reserved
) -> int:
    fps = list(iter_files(files))
    if not fps:
        print("[p2p_copy] send(): no files provided"); return 2
    src = fps[0]; size = src.stat().st_size

    hello = Hello(type="hello", code_hash_hex=code_to_hash_hex(code), role="sender").to_json()
    manifest = Manifest(type="manifest", entries=[ManifestEntry(path=src.name, size=size)]).to_json()

    async with connect(server, max_size=None) as ws:
        await ws.send(hello)
        await ws.send(manifest)
        with src.open("rb") as fp:
            for chunk in read_in_chunks(fp):
                await ws.send(chunk)
        await ws.send(EOF)
    return 0

async def receive(
        *, server: str, code: str,
        resume: bool = True,  # reserved
        out: Optional[str] = None,
) -> int:
    hello = Hello(type="hello", code_hash_hex=code_to_hash_hex(code), role="receiver").to_json()
    dest_dir = Path(out or os.getcwd()); dest_dir.mkdir(parents=True, exist_ok=True)

    async with connect(server, max_size=None) as ws:
        await ws.send(hello)

        # manifest (Text) erwarten
        msg = await ws.recv()
        if isinstance(msg, bytes):
            print("[p2p_copy] receive(): expected manifest, got binary"); return 3
        obj = loads(msg)
        if obj.get("type") != "manifest":
            print("[p2p_copy] receive(): expected manifest, got", obj); return 3
        entries = obj.get("entries") or []
        if not entries:
            print("[p2p_copy] receive(): empty manifest"); return 3
        entry = entries[0]
        dest_path = dest_dir / entry["path"]
        ensure_dir(dest_path.parent)

        # Datenframes (binär) bis EOF sammeln
        with dest_path.open("wb") as outfp:
            async for frame in ws:
                if isinstance(frame, bytes):
                    outfp.write(frame)
                else:
                    try:
                        o = json.loads(frame)
                    except Exception:
                        print("[p2p_copy] receive(): unexpected text frame", frame); return 4
                    if o.get("type") == "eof":
                        break
                    else:
                        print("[p2p_copy] receive(): unexpected control", o); return 4
    return 0
