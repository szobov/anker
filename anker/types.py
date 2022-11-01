from __future__ import annotations

import dataclasses
import enum
import typing as _t


@enum.unique
class ANKI_BASE_URL_TYPE(enum.Enum):
    WEB = enum.auto()
    USER = enum.auto()


TokenT = dict[str, str]


@dataclasses.dataclass(frozen=True)
class NoteTypeInfo:
    note_id: str
    note_name: str


@dataclasses.dataclass(frozen=True)
class LoginForm:
    username: str
    password: str
    csrf_token: str
    submited: str = "1"

    def to_dict(self) -> dict[str, str]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class UserInfo:
    username: str
    token: TokenT
    usernet_token: TokenT
    card_token: str


@dataclasses.dataclass(frozen=True)
class DeckInfo:
    deck_name: str
    deck_id: str


@dataclasses.dataclass(frozen=True)
class FieldInfo:
    config: dict[str, _t.Any]
    field_name: str
    order: int

    @classmethod
    def from_dict(cls: _t.Type[FieldInfo], field_info: dict[str, _t.Any]) -> FieldInfo:
        order = field_info["ord"]
        if not order:
            order = {"val": 0}
        return cls(
            config=field_info["config"],
            field_name=field_info["name"],
            order=order["val"],
        )


@dataclasses.dataclass(frozen=True)
class CardInfo:
    front_text: str
    back_text: str


class BaseAnkerException(Exception):
    ...
