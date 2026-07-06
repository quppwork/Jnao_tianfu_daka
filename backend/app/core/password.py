"""密码哈希 — hashlib"""

import hashlib
import os


def hash_password(plain: str) -> str:
    salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + plain).encode("utf-8")).hexdigest()
    return f"{salt}${h}"


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    parts = hashed.split("$", 1)
    if len(parts) != 2:
        return False
    salt, h = parts
    return hashlib.sha256((salt + plain).encode("utf-8")).hexdigest() == h
