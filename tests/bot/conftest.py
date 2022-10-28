from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mocked_telebot() -> MagicMock:
    return MagicMock()
