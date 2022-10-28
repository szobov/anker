import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


@lru_cache(maxsize=1)
def get_key() -> bytes:
    key = os.getenv("ANKER_PEPPER_KEY")
    assert key
    return key.strip().encode()


@lru_cache(maxsize=1)
def get_fernet() -> Fernet:
    return Fernet(get_key())


def encrypt_message(message: str) -> str:
    return get_fernet().encrypt(message.encode()).decode()


def decrypt_message(encrypted_message: str) -> str:
    if len(encrypted_message) == "":
        return ""
    try:
        return get_fernet().decrypt(encrypted_message.encode()).decode()
    except (InvalidToken, UnicodeError):
        return ""
