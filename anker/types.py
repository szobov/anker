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
    note_id: int
    note_name: str


@dataclasses.dataclass(frozen=True)
class UserInfo:
    username: str
    token: TokenT
    usernet_token: TokenT


@dataclasses.dataclass(frozen=True)
class DeckInfo:
    deck_name: str
    deck_id: int


@dataclasses.dataclass(frozen=True)
class FieldInfo:
    config: dict[str, _t.Any]
    field_name: str
    order: int


@dataclasses.dataclass(frozen=True)
class CardInfo:
    front_text: str
    back_text: str


class BaseAnkerException(Exception):
    ...
