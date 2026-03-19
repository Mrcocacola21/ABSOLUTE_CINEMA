"""Password hashing helpers."""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordHasher:
    """Utility class encapsulating password hashing operations."""

    def hash_password(self, password: str) -> str:
        """Hash a plain-text password."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain-text password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)


password_hasher = PasswordHasher()
