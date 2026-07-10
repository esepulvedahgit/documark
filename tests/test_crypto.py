from apps.core import crypto


def test_encrypt_decrypt_bytes_roundtrip():
    data = b"hola mundo, contenido secreto"
    token = crypto.encrypt_bytes(data)
    assert token != data
    assert crypto.decrypt_bytes(token) == data


def test_encrypt_decrypt_file_roundtrip(tmp_path):
    original = tmp_path / "plain.md"
    original.write_text("# Título\n\ncontenido", encoding="utf-8")

    encrypted = tmp_path / "plain.md.enc"
    crypto.encrypt_file(original, encrypted)

    assert encrypted.exists()
    # The on-disk ciphertext must not contain the plaintext.
    assert b"contenido" not in encrypted.read_bytes()

    recovered = crypto.decrypt_file_to_bytes(encrypted)
    assert recovered.decode("utf-8") == "# Título\n\ncontenido"


def test_decrypt_invalid_token_raises():
    import pytest

    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_bytes(b"not-a-valid-fernet-token")
