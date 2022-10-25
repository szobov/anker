import os

from cryptography.fernet import Fernet

from anker import encryption


def test_encryption():
    os.environ["ANKER_PEPPER_KEY"] = Fernet.generate_key().decode()
    test_message = "test message 123"
    encrypted_message = encryption.encrypt_message(test_message)
    assert encrypted_message != test_message
    decrypted_message = encryption.decrypt_message(encrypted_message)
    assert decrypted_message == test_message
    os.environ.pop("ANKER_PEPPER_KEY")
