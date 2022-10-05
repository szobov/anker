from __future__ import annotations

import json
import logging
import typing as _t

import requests
from bs4 import BeautifulSoup

from .types import (
    ANKI_BASE_URL_TYPE,
    CardInfo,
    DeckInfo,
    FieldInfo,
    LoginForm,
    NoteTypeInfo,
    UserInfo,
)

logger = logging.getLogger(__name__)

ANKI_COOKIE_NAME = "ankiweb"
ANKIUSER_DOMAIN = "ankiuser.net"
ANKIWEB_URL = "https://ankiweb.net"
ANKIUSER_URL = f"https://{ANKIUSER_DOMAIN}"


def make_url(base_url_type: ANKI_BASE_URL_TYPE, endpoint: str) -> str:
    base_url: str
    match base_url_type:
        case ANKI_BASE_URL_TYPE.WEB:
            base_url = ANKIWEB_URL
        case ANKI_BASE_URL_TYPE.USER:
            base_url = ANKIUSER_URL
    return f"{base_url}/{endpoint}"


def get_card_csrf_token(html_page: str) -> str:
    start_token = "new anki.Editor('"
    start_substring_index = html_page.find(start_token)
    if start_substring_index == -1:
        raise RuntimeError
    start_substring_index += len(start_token)
    end_substing_index = start_substring_index + html_page[start_substring_index:].find(
        "',"
    )
    return html_page[start_substring_index:end_substing_index]


def get_csrf_token(html_page: str) -> str:
    html = BeautifulSoup(html_page, features="lxml")
    csrf_input = html.select_one("input[name='csrf_token']")
    assert csrf_input is not None, csrf_input
    return csrf_input["value"]


def login(username: str, password: str) -> UserInfo:
    logger.info(msg={"comment": "login end extract token", "user": username})
    url = make_url(ANKI_BASE_URL_TYPE.WEB, "account/login")
    login_page_response = requests.get(url)
    assert login_page_response.ok

    form = LoginForm(
        username=username,
        password=password,
        csrf_token=get_csrf_token(login_page_response.text),
    )

    response = requests.post(
        url, data=form.to_dict(), cookies=login_page_response.cookies
    )
    assert response.ok, response.text
    request_cookies: requests.cookies.RequestsCookieJar = getattr(
        response.request, "_cookies"
    )
    assert ANKI_COOKIE_NAME in request_cookies, request_cookies
    logger.info(msg={"comment": "token is extracted", "user": username})
    token = {ANKI_COOKIE_NAME: request_cookies[ANKI_COOKIE_NAME]}

    url = make_url(ANKI_BASE_URL_TYPE.USER, "edit/")
    edit_page_response = requests.get(url, cookies=token, verify=False)
    assert edit_page_response.ok, edit_page_response.text
    request_cookies = getattr(edit_page_response.request, "_cookies")
    usernet_token = next(
        filter(
            lambda c: c.domain == ANKIUSER_DOMAIN and c.name == ANKI_COOKIE_NAME,
            request_cookies,
        ),
        None,
    )
    assert usernet_token
    assert usernet_token.value
    card_token = get_card_csrf_token(edit_page_response.text)

    return UserInfo(
        username=username,
        token=token,
        usernet_token={ANKI_COOKIE_NAME: usernet_token.value},
        card_token=card_token,
    )


def create_deck(user_info: UserInfo, deck_name: str):
    logger.info(msg={"comment": "create a deck", "user": user_info.username})
    url = make_url(ANKI_BASE_URL_TYPE.WEB, "decks/create")
    data = {"name": deck_name}
    headers = {"x-requested-with": "XMLHttpRequest"}
    response = requests.get(url, cookies=user_info.token, params=data, headers=headers)
    if not response.ok:
        logger.warning(
            msg={
                "comment": "failed to create a deck",
                "response": response.text,
                "status": response.status_code,
            }
        )
        raise RuntimeError  # TODO: use packet-wide exceptions

    logger.info(msg={"comment": "deck has been created"})


def get_decks_and_note_types(
    user_info: UserInfo,
) -> tuple[dict[str, DeckInfo], dict[str, NoteTypeInfo]]:
    logger.info(msg={"comment": "get decks and note types", "user": user_info.username})
    url = make_url(ANKI_BASE_URL_TYPE.USER, "edit/getAddInfo")
    response = requests.get(url, cookies=user_info.token, verify=False)
    if response.status_code != 200:
        raise RuntimeError  # TODO: use packet-wide exceptions
    content: dict[str, _t.Any] = {}
    try:
        content = response.json()
    except requests.exceptions.JSONDecodeError:
        logger.exception(msg={""})
        raise RuntimeError("")
    decks: dict[str, DeckInfo] = {
        d["name"]: DeckInfo(deck_name=d["name"], deck_id=d["id"])
        for d in content["decks"]
    }
    note_types: dict[str, NoteTypeInfo] = {
        n["name"]: NoteTypeInfo(note_id=n["id"], note_name=n["name"])
        for n in content["notetypes"]
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
    url = make_url(ANKI_BASE_URL_TYPE.USER, "edit/getNotetypeFields")
    response = requests.get(
        url,
        cookies=user_info.usernet_token,
        params={"ntid": note_type.note_id},
        verify=False,
    )
    assert response.status_code == 200, response.text
    if response.status_code != 200:
        raise RuntimeError  # TODO: use packet-wide exceptions
    try:
        content = response.json()
    except requests.exceptions.JSONDecodeError:
        logger.exception(msg={""})
        raise RuntimeError("")
    return [FieldInfo.from_dict(f) for f in content["fields"]]


def add_card_to_deck(
    user_info: UserInfo,
    deck_info: DeckInfo,
    note_type: NoteTypeInfo,
    fields_info: list[FieldInfo],
    card_info: CardInfo,
):
    logger.info(msg={"comment": "add a card", "user": user_info.username})
    url = make_url(ANKI_BASE_URL_TYPE.USER, "edit/save")

    fields_array: list[str] = []
    for field in sorted(fields_info, key=lambda f: f.order):
        match field.field_name:
            case "Back":
                fields_array.append(card_info.back_text)
            case "Front":
                fields_array.append(card_info.front_text)
            case _:
                fields_array.append("")
    tags = ""

    card_data_with_tag = [fields_array, tags]

    data = {
        "nid": "",
        "data": json.dumps(card_data_with_tag),
        "csrf_token": user_info.card_token,
        "mid": note_type.note_id,
        "deck": deck_info.deck_id,
    }

    response = requests.post(
        url, data=data, cookies=user_info.usernet_token, verify=False
    )
    assert response.status_code == 200, response.text

    content: list[str | list[str]] = []
    try:
        content = response.json()
    except requests.exceptions.JSONDecodeError:
        logger.exception(msg={""})
        raise RuntimeError("")
    assert content == card_data_with_tag, content


def main():
    import os

    password = os.getenv("ANKI_PASSWORD")
    username = os.getenv("ANKI_USERNAME")
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
