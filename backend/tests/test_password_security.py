"""
Unit tests for password hashing and verification using bcrypt directly.
"""
import pytest
from app.core.security import hash_password, verify_password


def test_password_security_round_trip():
    # 1. Test basic round trip
    password = "MySecurePassword123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True

    # 2. Test incorrect password fails verification
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False


def test_password_security_long_password():
    # 3. Test password longer than 72 bytes
    long_password = "a" * 100
    hashed = hash_password(long_password)
    assert verify_password(long_password, hashed) is True

    # Truncated versions (72 bytes vs >72 bytes)
    truncated_72 = "a" * 72
    assert verify_password(truncated_72, hashed) is True

    # Slightly different at byte 73 should still match due to 72-byte truncation
    mutated_long = ("a" * 72) + "b" * 28
    assert verify_password(mutated_long, hashed) is True

    # Mutated within the first 72 bytes should fail
    mutated_short = "b" + ("a" * 99)
    assert verify_password(mutated_short, hashed) is False
