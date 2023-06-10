from unittest.mock import MagicMock

import pytest
import responses


@pytest.fixture
def mocked_telebot() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mocked_http_requests():
    with responses.RequestsMock() as mock:
        yield mock
