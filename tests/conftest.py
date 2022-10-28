import os

import pytest
from cryptography.fernet import Fernet


@pytest.fixture
def encryption_env_key():
    os.environ["ANKER_PEPPER_KEY"] = Fernet.generate_key().decode()
    yield
    os.environ.pop("ANKER_PEPPER_KEY")
