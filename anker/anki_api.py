from __future__ import annotations

import logging

import requests

from .anki_proto import (
    first_login_pb2,
    login_pb2,
    create_deck_pb2,
    add_info_pb2,
    get_notetype_fields_pb2,
    add_note_pb2,
)


from .types import (
    ANKI_BASE_URL_TYPE,
    BaseAnkerException,
    CardInfo,
    DeckInfo,
    FieldInfo,
    NoteTypeInfo,
    UserInfo,
)

logger = logging.getLogger(__name__)

ANKI_COOKIE_NAME = "ankiweb"
ANKIUSER_DOMAIN = "ankiuser.net"
ANKIWEB_URL = "https://ankiweb.net"
ANKIUSER_URL = f"https://{ANKIUSER_DOMAIN}"
REQUEST_TIMEOUT_S = 5


class AnkiAuthorizationException(BaseAnkerException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


def make_url(base_url_type: ANKI_BASE_URL_TYPE, endpoint: str) -> str:
    base_url: str
    match base_url_type:
        case ANKI_BASE_URL_TYPE.WEB:
            base_url = ANKIWEB_URL
        case ANKI_BASE_URL_TYPE.USER:
            base_url = ANKIUSER_URL
    return f"{base_url}/{endpoint}"


def _get_headers(is_xml_http_request: bool = False) -> dict[str, str]:
    headers = {"Content-Type": "application/octet-stream"}
    if is_xml_http_request:
        headers["x-requested-with"] = "XMLHttpRequest"
    return headers


def login(username: str, password: str) -> UserInfo:
    logger.info(msg={"comment": "login end extract token", "user": username})
    url = make_url(ANKI_BASE_URL_TYPE.WEB, "svc/account/login")

    first_login_msg = first_login_pb2.FirstLogin()
    first_login_msg.login = username
    first_login_msg.password = password

    ankiweb_login_response = requests.post(
        url,
        headers=_get_headers(),
        data=first_login_msg.SerializeToString(),
        timeout=REQUEST_TIMEOUT_S,
    )

    assert ankiweb_login_response.ok, ankiweb_login_response.content

    msg = login_pb2.LoginResponse()
    msg.ParseFromString(ankiweb_login_response.content)

    assert msg.status == login_pb2.LOGIN_RESPONSE_STATUS_AUTHENTICATED, msg.status

    url = make_url(ANKI_BASE_URL_TYPE.USER, "account/ankiuser-login")
    ankiuser_login_response = requests.get(
        url,
        params={"t": msg.token},
        allow_redirects=True,
        timeout=REQUEST_TIMEOUT_S,
    )
    assert ankiuser_login_response.ok, ankiuser_login_response.content

    request_cookies: requests.cookies.RequestsCookieJar = getattr(
        ankiuser_login_response.request, "_cookies"
    )
    assert ANKI_COOKIE_NAME in request_cookies, request_cookies
    logger.info(msg={"comment": "token is extracted", "user": username})
    usernet_token = {
        ANKI_COOKIE_NAME: request_cookies[ANKI_COOKIE_NAME],
        "has_auth": "1",
    }
    ankiweb_token = {
        ANKI_COOKIE_NAME: ankiweb_login_response.cookies[ANKI_COOKIE_NAME],
        "has_auth": "1",
    }
    return UserInfo(username=username, token=ankiweb_token, usernet_token=usernet_token)


def create_deck(user_info: UserInfo, deck_name: str):
    logger.info(msg={"comment": "create a deck", "user": user_info.username})
    url = make_url(ANKI_BASE_URL_TYPE.WEB, "decks/create")

    create_deck_msg = create_deck_pb2.CreateDeck()
    create_deck_msg.name = deck_name

    headers = _get_headers(is_xml_http_request=True)
    url = make_url(ANKI_BASE_URL_TYPE.WEB, "svc/decks/create-deck")
    create_deck_response = requests.post(
        url,
        cookies=user_info.token,
        headers=headers,
        data=create_deck_msg.SerializeToString(),
        timeout=REQUEST_TIMEOUT_S,
    )
    if not create_deck_response.ok:
        logger.warning(
            msg={
                "comment": "failed to create a deck",
                "response": create_deck_response.text,
                "status": create_deck_response.status_code,
            }
        )
        if create_deck_response.status_code == 403:
            raise AnkiAuthorizationException()
        raise RuntimeError  # TODO: use packet-wide exceptions

    logger.info(msg={"comment": "deck has been created"})


def get_decks_and_note_types(
    user_info: UserInfo,
) -> tuple[dict[str, DeckInfo], dict[str, NoteTypeInfo]]:
    logger.info(msg={"comment": "get decks and note types", "user": user_info.username})
    url = make_url(ANKI_BASE_URL_TYPE.USER, "svc/editor/get-info-for-adding")
    response = requests.post(
        url,
        cookies=user_info.usernet_token,
        timeout=REQUEST_TIMEOUT_S,
        headers=_get_headers(),
    )
    if not response.ok:
        if response.status_code == 403:
            raise AnkiAuthorizationException()
        raise RuntimeError  # TODO: use packet-wide exceptions

    add_info_msg = add_info_pb2.AddInfo()
    add_info_msg.ParseFromString(response.content)
    decks: dict[str, DeckInfo] = {
        d.name: DeckInfo(deck_name=d.name, deck_id=d.id) for d in add_info_msg.decks
    }
    note_types: dict[str, NoteTypeInfo] = {
        n.name: NoteTypeInfo(note_id=n.id, note_name=n.name)
        for n in add_info_msg.notetypes
    }
    return decks, note_types


def get_note_type_fields(
    user_info: UserInfo, note_type: NoteTypeInfo
) -> list[FieldInfo]:
    logger.info(
        msg={
            "comment": "get fields of a note type",
            "user": user_info.username,
            "note": note_type,
        }
    )
    get_notetype_fields_msg = get_notetype_fields_pb2.GetNotetypeFieldsRequest()
    get_notetype_fields_msg.notetypeId = note_type.note_id
    url = make_url(ANKI_BASE_URL_TYPE.USER, "svc/editor/get-notetype-fields")
    response = requests.post(
        url,
        cookies=user_info.usernet_token,
        data=get_notetype_fields_msg.SerializeToString(),
        timeout=REQUEST_TIMEOUT_S,
        headers=_get_headers(),
    )
    if not response.ok:
        if response.status_code == 403:
            raise AnkiAuthorizationException()
        raise RuntimeError  # TODO: use packet-wide exceptions
    get_notetype_fields_response = get_notetype_fields_pb2.GetNotetypeFieldsResponse()
    get_notetype_fields_response.ParseFromString(response.content)

    return [
        FieldInfo(
            order=f.ord.val,
            field_name=f.name,
            config=f.config,
        )
        for f in get_notetype_fields_response.fields
    ]


def add_card_to_deck(
    user_info: UserInfo,
    deck_info: DeckInfo,
    note_type: NoteTypeInfo,
    fields_info: list[FieldInfo],
    card_info: CardInfo,
):
    logger.info(msg={"comment": "add a card", "user": user_info.username})
    url = make_url(ANKI_BASE_URL_TYPE.USER, "svc/editor/add-or-update")

    fields_array: list[str] = []
    for field in sorted(fields_info, key=lambda f: f.order):
        match field.field_name:
            case "Back":
                fields_array.append(card_info.back_text)
            case "Front":
                fields_array.append(card_info.front_text)
            case _:
                fields_array.append("")

    msg = add_note_pb2.AddNote()
    msg.fields.extend(fields_array)
    msg.add.deckId = deck_info.deck_id
    msg.add.notetypeId = note_type.note_id

    response = requests.post(
        url,
        data=msg.SerializeToString(),
        cookies=user_info.usernet_token,
        timeout=REQUEST_TIMEOUT_S,
        headers=_get_headers(),
    )
    if not response.ok:
        if response.status_code == 403:
            raise AnkiAuthorizationException()
        raise RuntimeError  # TODO: use packet-wide exceptions


def main():
    import os

    password = os.getenv("ANKI_PASSWORD")
    username = os.getenv("ANKI_USERNAME")
    assert password is not None
    assert username is not None
    user_info = login(username=username, password=password)
    test_deck_name = "New Тест Deck 2"
    create_deck(user_info, test_deck_name)

    decks, note_types = get_decks_and_note_types(user_info)
    assert test_deck_name in decks
    deck_info = decks[test_deck_name]

    expected_node_type_name = "Basic (and reversed card)"
    assert expected_node_type_name in note_types
    note_type = note_types[expected_node_type_name]
    note_type_fields = get_note_type_fields(user_info, note_type)
    assert {"Front", "Back"} == set((f.field_name for f in note_type_fields))
    import time

    test_card_info = CardInfo(
        front_text=f"Created from WoW at {time.monotonic()}",
        back_text="the answer is 42",
    )
    add_card_to_deck(
        user_info, deck_info, note_type, note_type_fields, card_info=test_card_info
    )


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    main()
