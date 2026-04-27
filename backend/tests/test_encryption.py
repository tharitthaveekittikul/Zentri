import pytest
from app.core.encryption import encrypt, decrypt


def test_encrypt_decrypt_roundtrip():
    plaintext = "sk-ant-api03-secret-key-12345"
    token = encrypt(plaintext)
    assert token != plaintext
    assert decrypt(token) == plaintext


def test_different_plaintexts_produce_different_ciphertexts():
    a = encrypt("key-a")
    b = encrypt("key-b")
    assert a != b


def test_same_plaintext_produces_different_ciphertexts():
    # nonce is random — same input should not produce same output
    a = encrypt("same-key")
    b = encrypt("same-key")
    assert a != b
    assert decrypt(a) == decrypt(b) == "same-key"
