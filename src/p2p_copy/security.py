import hashlib
import os

from p2p_copy.protocol import EncryptedManifest

def import_optional_security_libs():
    global hash_secret_raw, Type, AESGCM
    try:
        # security libs are needed if encryption is used
        from argon2.low_level import hash_secret_raw, Type
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ModuleNotFoundError as E:
        raise ModuleNotFoundError(E.msg + '\nTo use encryption optional security libs are needed (pip install ".[security]")')

def _get_argon2_hash(code: str, salt: bytes) -> bytes:
    import_optional_security_libs()
    return hash_secret_raw(
        secret=code.encode(),
        salt=salt,
        time_cost=3,
        memory_cost=32 * 2**10,       # 32 MiB * 8 threads
        parallelism=8,
        hash_len=32,
        type=Type.ID
    )

class SecurityHandler:
    def __init__(self, code: str, encrypt: bool):
        self.encrypt = encrypt
        if self.encrypt:
            import_optional_security_libs()
            self.code_hash = _get_argon2_hash(code, b"code_hash used for hello-match")
            self.nonce_hasher = ChainedChecksum()
            self.cipher = AESGCM(_get_argon2_hash(code, b"cipher used for E2E-encryption"))
        else:
            self.code_hash = hashlib.sha256(code.encode()).digest()

    def encrypt_chunk(self, chunk:bytes) -> bytes:
        if self.encrypt:
            return self.cipher.encrypt(self.nonce_hasher.next_hash(), chunk, None)
        return chunk

    def decrypt_chunk(self, chunk:bytes) -> bytes:
        if self.encrypt:
            return self.cipher.decrypt(self.nonce_hasher.next_hash(), chunk, None)
        return chunk

    def build_encrypted_manifest(self, manifest: str) -> str:
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
    Generates chained checksum over binary, potentially compressed, chunks of a file.
    """

    def __init__(self, seed: bytes = b"") -> None:
        self.prev_chain = seed

    def next_hash(self, payload: bytes = b"") -> bytes:
        h = hashlib.sha256()
        h.update(self.prev_chain)
        h.update(payload)
        self.prev_chain = h.digest()
        return self.prev_chain



