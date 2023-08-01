from __future__ import annotations

import dataclasses
import enum
import logging
import typing as _t

from anker import encryption
from anker.types import DeckInfo, NoteTypeInfo, UserInfo

logger = logging.getLogger(__name__)


@enum.unique
class ClientStates(enum.IntEnum):
    UNAUTHORIZED = 1
    SET_USER_EMAIL = 2
    SET_PASSWORD = 3
    SELECT_DECK = 4
    CREATE_NEW_DECK = 5
    AUTHORIZED = 6
    SELECT_LANG = 7


def _filter_unexpected_fields_for_dataclass(
    data: dict[str, _t.Any], expected_fields: _t.Iterable[dataclasses.Field]
) -> dict[str, _t.Any]:
    expected_field_names = {f.name for f in expected_fields}
    return {k: v for k, v in data.items() if k in expected_field_names}


@dataclasses.dataclass(frozen=True)
class ClientState:
    anki_user_email: str
    anki_password: str
    language_from: str
    language_to: str
    anki_user_info: _t.Optional[UserInfo] = None
    anki_deck_info: _t.Optional[DeckInfo] = None
    anki_note_type_info: _t.Optional[NoteTypeInfo] = None
    state: ClientStates = ClientStates.UNAUTHORIZED

    @classmethod
    def identity(cls: _t.Type[ClientState]) -> ClientState:
        return cls(
            anki_user_email="",
            anki_password="",
            language_from="",
            language_to="",
            anki_user_info=None,
            anki_deck_info=None,
            anki_note_type_info=None,
            state=ClientStates.UNAUTHORIZED,
        )

    def make_from(self, **changes: _t.Any) -> ClientState:
        return dataclasses.replace(self, **changes)

    def get_encrypted(self) -> dict[str, str | int | dict[str, str] | None]:
        encrypted_anki_password = ""
        if self.anki_password:
            encrypted_anki_password = encryption.encrypt_message(self.anki_password)
        deck_info = None
        if self.anki_deck_info:
            deck_info = dataclasses.asdict(self.anki_deck_info)
        user_info = None
        if self.anki_user_info:
            user_info = dataclasses.asdict(self.anki_user_info)
        note_type = None
        if self.anki_note_type_info:
            note_type = dataclasses.asdict(self.anki_note_type_info)
        return {
            "anki_user_email": self.anki_user_email,
            "anki_password": encrypted_anki_password,
            "language_from": self.language_from,
            "language_to": self.language_to,
            "state": self.state.value,
            "anki_deck_info": deck_info,
            "anki_user_info": user_info,
            "anki_note_type_info": note_type,
        }

    @classmethod
    def from_encrypted(
        cls: _t.Type[ClientState], data: dict[str, _t.Any]
    ) -> ClientState | None:
        try:
            anki_user_info = None
            if data["anki_user_info"] and isinstance(
                data["anki_user_info"], _t.Mapping
            ):
                anki_user_info = UserInfo(
                    **_filter_unexpected_fields_for_dataclass(
                        data["anki_user_info"], dataclasses.fields(UserInfo)
                    )
                )
            anki_deck_info = None
            if data["anki_deck_info"] and isinstance(
                data["anki_deck_info"], _t.Mapping
            ):
                anki_deck_info = DeckInfo(
                    **_filter_unexpected_fields_for_dataclass(
                        data["anki_deck_info"], dataclasses.fields(DeckInfo)
                    )
                )
            anki_note_type_info = None
            if data["anki_note_type_info"] and isinstance(
                data["anki_note_type_info"], _t.Mapping
            ):
                anki_note_type_info = NoteTypeInfo(
                    **_filter_unexpected_fields_for_dataclass(
                        data["anki_note_type_info"], dataclasses.fields(NoteTypeInfo)
                    )
                )
            return cls(
                anki_user_email=data["anki_user_email"],
                anki_password=encryption.decrypt_message(data["anki_password"]),
                language_from=data["language_from"],
                language_to=data["language_to"],
                state=ClientStates(int(data["state"])),
                anki_user_info=anki_user_info,
                anki_deck_info=anki_deck_info,
                anki_note_type_info=anki_note_type_info,
            )
        except (KeyError, RuntimeError, TypeError):
            logger.exception(
                msg={"comment": "Catch an exception while parsing client's state"}
            )
            return None
