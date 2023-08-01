import json

import requests
import responses
import pytest

from anker import anki_api, types


@pytest.mark.skip(reason="The API is changed")
def test_login(
    mocked_http_requests: responses.RequestsMock, login_html: str, edit_html: str
):

    test_ankiweb_token = "AnKiWeBtOkEn123"

    def logit_request_callback(request):
        headers = {
            "set-cookie": f"ankiweb={test_ankiweb_token}",
        }
        return (200, headers, login_html)

    mocked_http_requests.add_callback(
        responses.GET,
        "https://ankiweb.net/account/login",
        callback=logit_request_callback,
        content_type="text/html",
    )

    mocked_http_requests.post(
        "https://ankiweb.net/account/login",
        body="",
        status=200,
        content_type="text/html",
    )

    test_ankiuser_token = "AnKiUsErtOkEn123"

    def edit_request_callback(request):
        request._cookies = [
            requests.cookies.RequestsCookieJar().set(
                value=test_ankiuser_token, domain="ankiuser.net", name="ankiweb"
            )
        ]
        headers = {
            "set-cookie": f"ankiweb={test_ankiuser_token}; domain=ankiuser.net;",
        }
        return (200, headers, edit_html)

    mocked_http_requests.add_callback(
        responses.GET,
        url="https://ankiuser.net/edit/",
        content_type="text/html",
        callback=edit_request_callback,
    )
    test_username = "user@name.42"
    test_password = "42istheanswer"
    actual_user_info = anki_api.login(test_username, test_password)
    expected_user_info = types.UserInfo(
        username=test_username,
        token={"ankiweb": test_ankiweb_token},
        usernet_token={"ankiweb": test_ankiuser_token},
    )
    assert actual_user_info == expected_user_info


@pytest.mark.skip(reason="The API is changed")
def test_create_deck(user_info, mocked_http_requests):
    expected_deck_name = "test_deck"
    expected_params = {"name": expected_deck_name}
    mocked_http_requests.get(
        "https://ankiweb.net/decks/create",
        body="",
        status=200,
        content_type="text/html",
        match=[
            responses.matchers.query_param_matcher(expected_params),
            responses.matchers.header_matcher(
                {"Cookie": f"ankiweb={user_info.token['ankiweb']}"}
            ),
        ],
    )
    anki_api.create_deck(user_info, expected_deck_name)


@pytest.mark.skip(reason="The API is changed")
def test_get_decks_and_note_types(
    user_info, mocked_http_requests, note_type_info, deck_info
):
    expected_note_type = note_type_info
    expected_deck = deck_info
    mocked_http_requests.get(
        "https://ankiuser.net/edit/getAddInfo",
        json={
            "notetypes": [
                {"id": expected_note_type.note_id, "name": expected_note_type.note_name}
            ],
            "decks": [{"id": expected_deck.deck_id, "name": expected_deck.deck_name}],
            "currentDeckId": "1",
            "currentNotetypeId": "1466496423776",
        },
        status=200,
        content_type="text/html",
        match=[
            responses.matchers.header_matcher(
                {"Cookie": f"ankiweb={user_info.token['ankiweb']}"}
            ),
        ],
    )
    (actual_decks, actual_note_types) = anki_api.get_decks_and_note_types(user_info)
    assert {expected_deck.deck_name: expected_deck} == actual_decks
    assert {expected_note_type.note_name: expected_note_type} == actual_note_types


@pytest.mark.skip(reason="The API is changed")
def test_add_card_to_deck(
    mocked_http_requests, user_info, card_info, note_type_info, fields_info, deck_info
):
    expected_card_data_with_tag = [["", "Test front text", "test back text"], ""]
    expected_card_data = {
        "nid": "",
        "data": json.dumps(expected_card_data_with_tag),
        "mid": note_type_info.note_id,
        "deck": deck_info.deck_id,
    }
    mocked_http_requests.post(
        "https://ankiuser.net/edit/save",
        json=expected_card_data_with_tag,
        status=200,
        content_type="text/html",
        match=[
            responses.matchers.header_matcher(
                {"Cookie": f"ankiweb={user_info.usernet_token['ankiweb']}"}
            ),
            responses.matchers.urlencoded_params_matcher(
                expected_card_data, allow_blank=True
            ),
        ],
    )
    anki_api.add_card_to_deck(
        user_info, deck_info, note_type_info, fields_info, card_info
    )


@pytest.mark.skip(reason="The API is changed")
def test_get_note_type_fields(
    mocked_http_requests, user_info, note_type_info, fields_info
):
    response = {
        "fields": [
            {
                "ord": {},
                "name": "ignored",
                "config": {},
            },
            {
                "ord": {"val": 1},
                "name": "Front",
                "config": {},
            },
            {
                "ord": {"val": 2},
                "name": "Back",
                "config": {},
            },
        ]
    }
    expected_params = {"ntid": note_type_info.note_id}
    mocked_http_requests.get(
        "https://ankiuser.net/edit/getNotetypeFields",
        json=response,
        status=200,
        content_type="text/html",
        match=[
            responses.matchers.header_matcher(
                {"Cookie": f"ankiweb={user_info.usernet_token['ankiweb']}"}
            ),
            responses.matchers.query_param_matcher(expected_params),
        ],
    )
    assert sorted(fields_info, key=lambda f: f.order) == anki_api.get_note_type_fields(
        user_info, note_type_info
    )
