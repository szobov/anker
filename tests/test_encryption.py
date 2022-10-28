import pytest

from anker import encryption


@pytest.mark.parametrize("input_text", ("", "test message 123"))
def test_encryption(input_text, encryption_env_key):
    test_message = input_text

    encrypted_message = encryption.encrypt_message(test_message)
    assert encrypted_message != test_message
    decrypted_message = encryption.decrypt_message(encrypted_message)
    assert decrypted_message == test_message


def test_invalid_input(encryption_env_key):
    assert encryption.decrypt_message("") == ""
    assert encryption.decrypt_message("ab") == ""
