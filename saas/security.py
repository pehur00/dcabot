"""
Security utilities for encrypting API keys and hashing passwords
"""
import os
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash, check_password_hash


# Load encryption key from environment
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY environment variable must be set")

cipher = Fernet(ENCRYPTION_KEY.encode())


def encrypt_api_key(api_key: str) -> str:
    """Encrypt user's exchange API key before storing in database"""
    if not api_key:
        raise ValueError("API key cannot be empty")
    return cipher.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt user's exchange API key when needed for bot execution"""
    if not encrypted:
        raise ValueError("Encrypted API key cannot be empty")
    return cipher.decrypt(encrypted.encode()).decode()


def hash_password(password: str) -> str:
    """Hash user password for storage (bcrypt via werkzeug)"""
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify user password against stored hash"""
    return check_password_hash(password_hash, password)


def generate_encryption_key():
    """Generate a new Fernet encryption key"""
    return Fernet.generate_key().decode()


if __name__ == '__main__':
    # Generate a new key
    print("New encryption key (add to .env):")
    print(f"ENCRYPTION_KEY={generate_encryption_key()}")
