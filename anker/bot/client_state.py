from __future__ import annotations

import dataclasses
import enum
import logging
import typing as _t

from anker import encryption

logger = logging.getLogger(__name__)


@enum.unique
class ClientStates(enum.IntEnum):
    UNAUTHORIZED = enum.auto()
    SET_USER_EMAIL = enum.auto()
    SET_PASSWORD = enum.auto()
    SELECT_DECK = enum.auto()
    CREATE_NEW_DECK = enum.auto()
    AUTHORIZED = enum.auto()


@dataclasses.dataclass(frozen=True)
class ClientState:
    anki_user_email: str
    anki_password: str
    deck_id: str
    language_from: str
    language_to: str
    state: ClientStates = ClientStates.UNAUTHORIZED

    @classmethod
    def identity(cls: _t.Type[ClientState]) -> ClientState:
        return cls(
            anki_user_email="",
            anki_password="",
            deck_id="",
            language_from="",
            language_to="",
        )

    def make_from(self, **changes: _t.Any) -> ClientState:
        return dataclasses.replace(self, **changes)

    def get_encrypted(self) -> dict[str, str | int]:
        encrypted_anki_password = ""
        if self.anki_password:
            encrypted_anki_password = encryption.encrypt_message(self.anki_password)
        encrypted_deck_id = ""
        if self.deck_id:
            encrypted_deck_id = encryption.encrypt_message(self.deck_id)
        return {
            "anki_user_email": self.anki_user_email,
            "anki_password": encrypted_anki_password,
            "deck_id": encrypted_deck_id,
            "language_from": self.language_from,
            "language_to": self.language_to,
            "state": self.state.value,
        }

    @classmethod
    def from_encrypted(
        cls: _t.Type[ClientState], data: dict[str, str]
    ) -> ClientState | None:
        try:
            return cls(
                anki_user_email=data["anki_user_email"],
                anki_password=encryption.decrypt_message(data["anki_password"]),
                deck_id=data["deck_id"],
                language_from=data["language_from"],
                language_to=data["language_to"],
                state=ClientStates(int(data["state"])),
            )
        except (KeyError, RuntimeError):
            logger.exception(
                msg={"comment": "Catch an exception while parsing client's state"}
            )
            return None
