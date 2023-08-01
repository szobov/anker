import pytest
import responses

from anker import types


@pytest.fixture
def mocked_http_requests():
    with responses.RequestsMock() as mock:
        yield mock


@pytest.fixture
def user_info() -> types.UserInfo:
    return types.UserInfo(
        username="test_user",
        token={"ankiweb": "token"},
        usernet_token={"ankiweb": "usertoken"},
        card_token="cardtoken",
    )


@pytest.fixture
def deck_info() -> types.DeckInfo:
    return types.DeckInfo(deck_name="Test deck", deck_id="42")


@pytest.fixture
def note_type_info() -> types.NoteTypeInfo:
    return types.NoteTypeInfo(note_id="56", note_name="Test note type")


@pytest.fixture
def fields_info() -> list[types.FieldInfo]:
    return [
        types.FieldInfo(config={}, field_name="Back", order=2),
        types.FieldInfo(config={}, field_name="ignored", order=0),
        types.FieldInfo(config={}, field_name="Front", order=1),
    ]


@pytest.fixture
def card_info() -> types.CardInfo:
    return types.CardInfo(front_text="Test front text", back_text="test back text")
