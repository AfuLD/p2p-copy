from __future__ import annotations
from typing import Iterable, Optional, Literal

async def send(
    *,
    files: Iterable[str],
    code: str,
    server: str,
    encrypt: bool = False,
    compress: Literal["auto", "on", "off"] = "auto",
    chunk_size: int = 1 << 20,
    resume: bool = True,
    out: Optional[str] = None,
) -> int:
    print("[p2p_copy] send(): skeleton called — no data sent yet.")
    return 0

async def receive(
    *,
    code: str,
    server: str,
    encrypt: bool = False,
    resume: bool = True,
    out: Optional[str] = None,
) -> int:
    print("[p2p_copy] receive(): skeleton called — no data received yet.")
    return 0
