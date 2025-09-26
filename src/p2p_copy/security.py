import hashlib
import os

from p2p_copy.protocol import EncryptedManifest


def import_optional_security_libs():
    """
    Import optional security libraries (argon2-cffi, cryptography) if encryption is used.
    """
    global hash_secret_raw, Type, AESGCM
    try:
        # security libs are needed if encryption is used
        from argon2.low_level import hash_secret_raw, Type
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ModuleNotFoundError as E:
        raise ModuleNotFoundError(
            E.msg + '\nTo use encryption optional security libs are needed (pip install ".[security]")')


def _get_argon2_hash(code: str, salt: bytes) -> bytes:
    """
    Compute Argon2 hash of the code using the given salt.

    Parameters
    ----------
    code : str
        The passphrase to hash.
    salt : bytes
        The salt to use.

    Returns
    -------
    bytes
        The 32-byte Argon2 hash.
    """
    import_optional_security_libs()
    return hash_secret_raw(
        secret=code.encode(),
        salt=salt,
        time_cost=3,
        memory_cost=32 * 2 ** 10,  # 32 MiB * 8 threads
        parallelism=8,
        hash_len=32,
        type=Type.ID
    )


class SecurityHandler:
    """
    Handle security operations like hashing, encryption, and decryption for transfers.

    Parameters
    ----------
    code : str
        The shared passphrase/code.
    encrypt : bool
        Whether to enable end-to-end encryption.
    """

    def __init__(self, code: str, encrypt: bool):
        self.encrypt = encrypt
        if self.encrypt:
            import_optional_security_libs()
            self.code_hash = _get_argon2_hash(code, b"code_hash used for hello-match")
            self.nonce_hasher = ChainedChecksum()
            self.cipher = AESGCM(_get_argon2_hash(code, b"cipher used for E2E-encryption"))
        else:
            self.code_hash = hashlib.sha256(code.encode()).digest()

    def encrypt_chunk(self, chunk: bytes) -> bytes:
        """
        Encrypt a chunk if encryption is enabled.

        Parameters
        ----------
        chunk : bytes
            The chunk to encrypt.

        Returns
        -------
        bytes
            The encrypted chunk, or original if not encrypted.
        """
        if self.encrypt:
            return self.cipher.encrypt(self.nonce_hasher.next_hash(), chunk, None)
        return chunk

    def decrypt_chunk(self, chunk: bytes) -> bytes:
        """
        Decrypt a chunk if encryption is enabled.

        Parameters
        ----------
        chunk : bytes
            The chunk to decrypt.

        Returns
        -------
        bytes
            The decrypted chunk, or original if not encrypted.
        """
        if self.encrypt:
            return self.cipher.decrypt(self.nonce_hasher.next_hash(), chunk, None)
        return chunk

    def build_encrypted_manifest(self, manifest: str) -> str:
        """
        Build an encrypted manifest for secure transmission.

        Parameters
        ----------
        manifest : str
            The plaintext manifest JSON.

        Returns
        -------
        str
            The JSON-serialized EncryptedManifest.
        """
        start_nonce = os.urandom(32)
        self.nonce_hasher.next_hash(start_nonce)
        enc_manifest = self.encrypt_chunk(manifest.encode())
        return EncryptedManifest(
            type="enc_manifest",
            nonce=start_nonce.hex(),
            hidden_manifest=enc_manifest.hex()
        ).to_json()


class ChainedChecksum:
    """
    Generate chained SHA-256 checksums over sequential payloads.

    Parameters
    ----------
    seed : bytes, optional
        Initial seed for the chain. Default is empty bytes.
    """

    def __init__(self, seed: bytes = b"") -> None:
        self.prev_chain = seed

    def next_hash(self, payload: bytes = b"") -> bytes:
        """
        Compute the next hash in the chain: sha256(prev_chain || payload).

        Parameters
        ----------
        payload : bytes, optional
            Data to include in this hash. Default is empty.

        Returns
        -------
        bytes
            The 32-byte hash, which becomes the new prev_chain.
        """
        h = hashlib.sha256()
        h.update(self.prev_chain)
        h.update(payload)
        self.prev_chain = h.digest()
        return self.prev_chain
