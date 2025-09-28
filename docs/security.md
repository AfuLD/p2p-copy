# Security

p2p-copy incorporates security measures for pairing, integrity, and optional confidentiality. The design is suitable for HPC and other restricted networks. Depending on which features are used, users can decide whether to elevate security or to maximize performance. For features overview, see [Features](./features.md). For installation with security extras, see [Installation](./installation.md).
>Note: open [Security in Pages](https://afuld.github.io/p2p-copy/security/) or [Security in docs](docs/security.md) for relative links to work. 

## Core Security Elements

- **Code Hashing for Pairing**: The shared code is hashed (SHA-256 by default) before transmission. With encryption, Argon2id is used for key derivation and resistance to brute-force attacks.
- **Transport Security**: Relay supports TLS (WSS) to protect against eavesdropping and man-in-the-middle attacks. Enabled via `--tls` with certificates.
- **Integrity Verification**: Chained SHA-256 checksums on chunks ensure data is not corrupted or reordered. 
- **No Relay Storage**: Data is forwarded in real-time; no persistence reduces exposure.

## Optional End-to-End Encryption

- **Enabled via `--encrypt`**: Uses AES-256-GCM for authenticity and confidentiality. Keys derived from the code via Argon2id (time_cost=3, memory_cost=32 MiB, parallelism=8).
- **AES-GCM-Nonce Management**: Chained nonces (SHA-256) prevent reuse and ensure uniqueness per chunk.
- **Scope**: Encrypts manifests, file headers, and payloads. Transport TLS remains independent.
- **Dependencies**: Requires `argon2-cffi` and `cryptography` (installed with `[security]` extras).
- **Performance Trade-off**: Adds CPU overhead. The actual transfer time should not noticeably increase.    
 

## Threat Model

- **Protections Against**:
    - Eavesdropping: TLS and optional E2EE.
    - Tampering: Checksums and GCM authentication.
    - Brute-Force Attacks: Hashed codes; long, random and unique codes are recommended.
    - Replay Attacks: Sequential nonces and checksums.
- **Limitations**: Weak codes are vulnerable to guessing. Theoretically no forward secrecy. 

## Best Practices

- Use TLS on the relay for all production deployments.
- Enable E2EE for confidential data.
- Generate strong codes.
- Verify certificates when connecting to public relays.

For code details, see `security.py` in [Module Layout](./layout.md). For common security issues, see [Troubleshooting](./troubleshooting.md).
