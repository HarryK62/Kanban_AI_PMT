import hashlib
import hmac
import re
import secrets

PBKDF2_ITERATIONS = 260_000
SALT_BYTES = 16
TOKEN_BYTES = 32

USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,32}$")


class WeakPasswordError(ValueError):
    """Raised when a password fails the minimum strength requirements."""


class InvalidUsernameError(ValueError):
    """Raised when a username fails the required format."""


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> None:
    if not USERNAME_PATTERN.match(username):
        raise InvalidUsernameError(
            "Username must be 3-32 characters and can include letters, numbers, "
            "dots, hyphens, or underscores."
        )


def validate_password_strength(password: str) -> None:
    checks = (
        len(password) >= 8,
        re.search(r"[A-Z]", password) is not None,
        re.search(r"[a-z]", password) is not None,
        re.search(r"\d", password) is not None,
        re.search(r"[^A-Za-z0-9]", password) is not None,
    )
    if not all(checks):
        raise WeakPasswordError(
            "Password must be at least 8 characters and include an uppercase "
            "letter, a lowercase letter, a number, and a symbol."
        )


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        salt, expected_hex = encoded_hash.split("$", 1)
    except ValueError:
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), expected_hex)


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)
