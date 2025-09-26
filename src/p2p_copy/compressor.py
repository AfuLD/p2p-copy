from enum import Enum
from typing import Optional

import zstandard as zstd


class CompressMode(str, Enum):
    """
    Enumeration of compression modes.
    """

    auto = "auto"
    on = "on"
    off = "off"


class Compressor:
    """
    Handle compression and decompression of chunks using Zstandard.

    Parameters
    ----------
    mode : CompressMode, optional
        Compression mode. Default is 'auto'.
    """

    def __init__(self, mode: CompressMode = CompressMode.auto):
        self.mode = mode
        self.cctx: Optional[zstd.ZstdCompressor] = zstd.ZstdCompressor(level=3) if mode != CompressMode.off else None
        self.dctx: Optional[zstd.ZstdDecompressor] = None
        self.use_compression: bool = mode == CompressMode.on
        self.compression_type: str = "zstd" if mode == CompressMode.on else "none"

    async def determine_compression(self, first_chunk: bytes) -> bytes:
        """
        Determine if compression should be used based on the first chunk (auto mode).

        Parameters
        ----------
        first_chunk : bytes
            The first chunk of data.

        Returns
        -------
        bytes
            The (possibly compressed) first chunk.
        """

        if self.mode == CompressMode.off:
            return first_chunk

        else:
            compressed = self.cctx.compress(first_chunk)
            if self.mode == CompressMode.on:
                return compressed

            elif self.mode == CompressMode.auto:
                # Auto mode: test first chunk
                compression_ratio = len(compressed) / len(first_chunk) if first_chunk else 1.0
                self.use_compression = compression_ratio < 0.95  # Enable if compressed size < 95% of original
                self.compression_type = "zstd" if self.use_compression else "none"
                return compressed if self.use_compression else first_chunk

    def compress(self, chunk: bytes) -> bytes:
        """
        Compress a chunk if compression is enabled.

        Parameters
        ----------
        chunk : bytes
            The chunk to compress.

        Returns
        -------
        bytes
            The compressed or original chunk.
        """
        """Compress a chunk if compression is enabled."""
        if self.use_compression and self.cctx:
            return self.cctx.compress(chunk)
        return chunk

    def decompress(self, chunk: bytes) -> bytes:
        """
        Decompress a chunk if decompression is set up.

        Parameters
        ----------
        chunk : bytes
            The chunk to decompress.

        Returns
        -------
        bytes
            The decompressed or original chunk.
        """

        if self.dctx:
            return self.dctx.decompress(chunk)
        return chunk

    def set_decompression(self, compression_type: str):
        """
        Set up the decompressor based on the compression type.

        Parameters
        ----------
        compression_type : str
            The type of compression ('zstd' or 'none').
        """

        self.dctx = zstd.ZstdDecompressor() if compression_type == "zstd" else None
