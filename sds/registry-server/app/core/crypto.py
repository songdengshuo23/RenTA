import base64
import secrets

from gmssl import func, sm3
from gmssl.sm4 import SM4_DECRYPT, SM4_ENCRYPT, CryptSM4

SM4_BLOCK_SIZE = 16


def _normalize_sm4_key(key_hex: str) -> bytes:
    normalized = key_hex.removeprefix("0x").removeprefix("0X")
    if len(normalized) != 32:
        raise ValueError("SM4 key must be exactly 16 bytes represented as 32 hex chars")
    try:
        return bytes.fromhex(normalized)
    except ValueError as exc:
        raise ValueError("SM4 key must contain only hexadecimal characters") from exc


def _pkcs7_pad(data: bytes, block_size: int = SM4_BLOCK_SIZE) -> bytes:
    padding_length = block_size - (len(data) % block_size)
    return data + bytes([padding_length]) * padding_length


def _pkcs7_unpad(data: bytes, block_size: int = SM4_BLOCK_SIZE) -> bytes:
    if not data or len(data) % block_size != 0:
        raise ValueError("Invalid SM4 ciphertext length")
    padding_length = data[-1]
    if padding_length < 1 or padding_length > block_size:
        raise ValueError("Invalid SM4 padding")
    if data[-padding_length:] != bytes([padding_length]) * padding_length:
        raise ValueError("Invalid SM4 padding")
    return data[:-padding_length]


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _urlsafe_b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode((data + "=" * (-len(data) % 4)).encode("ascii"))


def sm4_encrypt(plaintext: str, key_hex: str) -> str:
    key = _normalize_sm4_key(key_hex)
    iv = secrets.token_bytes(SM4_BLOCK_SIZE)
    cipher = CryptSM4()
    cipher.set_key(key, SM4_ENCRYPT)
    encrypted = cipher.crypt_cbc(iv, _pkcs7_pad(plaintext.encode("utf-8")))
    return _urlsafe_b64encode(iv + encrypted)


def sm4_decrypt(ciphertext: str, key_hex: str) -> str:
    key = _normalize_sm4_key(key_hex)
    raw = _urlsafe_b64decode(ciphertext)
    if len(raw) <= SM4_BLOCK_SIZE or len(raw) % SM4_BLOCK_SIZE != 0:
        raise ValueError("Invalid SM4 payload")
    cipher = CryptSM4()
    cipher.set_key(key, SM4_DECRYPT)
    decrypted = cipher.crypt_cbc(raw[:SM4_BLOCK_SIZE], raw[SM4_BLOCK_SIZE:])
    return _pkcs7_unpad(decrypted).decode("utf-8")


def sm3_hash(value: str, salt: str) -> str:
    data = f"{salt}:{value}".encode()
    return str(sm3.sm3_hash(func.bytes_to_list(data)))
