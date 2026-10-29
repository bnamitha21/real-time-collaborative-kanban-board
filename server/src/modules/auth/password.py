from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

ph = PasswordHasher()


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(hash_val: str, password: str) -> bool:
    try:
        return ph.verify(hash_val, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
