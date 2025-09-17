from enum import Enum
import zstandard as zstd
from typing import Optional, BinaryIO

from .chunker import CHUNK_SIZE

class CompressMode(str, Enum):
    auto = "auto"
    on = "on"
    off = "off"

class Compressor:
    def __init__(self, mode: CompressMode = CompressMode.auto):
        self.mode = mode
        self.cctx: Optional[zstd.ZstdCompressor] = zstd.ZstdCompressor(level=3) if mode != CompressMode.off else None
        self.dctx: Optional[zstd.ZstdDecompressor] = None
        self.use_compression: bool = mode == CompressMode.on
        self.compression_type: str = "zstd" if mode == CompressMode.on else "none"

    def determine_compression(self, fp: BinaryIO) -> tuple[bool, str]:
        """Determine if compression should be used for the file and return (use_compression, compression_type)."""
        if self.mode == CompressMode.auto:
            # Auto mode: test first chunk
            first_chunk = fp.read(CHUNK_SIZE)
            fp.seek(0)  # Reset file pointer after reading
            if not first_chunk:
                return False, "none"
            if self.cctx is None:
                return False, "none"
            compressed = self.cctx.compress(first_chunk)
            compression_ratio = len(compressed) / len(first_chunk) if first_chunk else 1.0
            self.use_compression = compression_ratio < 0.95  # Enable if compressed size < 95% of original
            self.compression_type = "zstd" if self.use_compression else "none"

    def compress(self, chunk: bytes) -> bytes:
        """Compress a chunk if compression is enabled."""
        if self.use_compression and self.cctx:
            return self.cctx.compress(chunk)
        return chunk

    def decompress(self, chunk: bytes) -> bytes:
        """Decompress a chunk if decompression is enabled."""
        if self.dctx:
            return self.dctx.decompress(chunk)
        return chunk

    def set_decompression(self, compression_type: str):
        """Set up decompression based on compression type."""
        self.dctx = zstd.ZstdDecompressor() if compression_type == "zstd" else None