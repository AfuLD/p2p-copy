# API Reference

This section documents the public API of `p2p_copy`. For module structure, see [Module Layout](./layout.md). Generated from source code docstrings.

## Core Functions

::: p2p_copy.api.send
::: p2p_copy.api.receive

## Security

::: p2p_copy.security.SecurityHandler
::: p2p_copy.security.ChainedChecksum

## Compression

::: p2p_copy.compressor.Compressor
::: p2p_copy.compressor.CompressMode

## Protocol

::: p2p_copy.protocol.Hello
::: p2p_copy.protocol.Manifest
::: p2p_copy.protocol.file_begin
::: p2p_copy.protocol.pack_chunk
::: p2p_copy.protocol.unpack_chunk

## IO Utilities

::: p2p_copy.io_utils.read_in_chunks
::: p2p_copy.io_utils.compute_chain_up_to
::: p2p_copy.io_utils.iter_manifest_entries
::: p2p_copy.io_utils.ensure_dir

## Relay (p2p_copy_server)

::: p2p_copy_server.run_relay

For api usage examples, see [Examples](../examples). For feature details, see [Features](./features.md).
