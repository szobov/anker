from __future__ import annotations

import logging
import os
from functools import partial

import telebot

from anker.bot import message_processing

logger = logging.getLogger(__name__)


def _check_message_type_and_expected_users(
    expected_users: set[int], message: telebot.types.Message
) -> bool:
    logger.debug(
        msg={
            "comment": "check message type and user",
            "user_id": message.from_user.id,
            "message_type": message.chat.type,
        }
    )
    if message.chat.type != "private":
        return False
    if message.from_user.id in expected_users:
        return True
    return False


def start_bot(bot_token: str, expected_users_ids: tuple[int, ...]):
    logger.info(
        msg={"comment": "start bot with expected users", "user": expected_users_ids}
    )
    check_function = partial(
        _check_message_type_and_expected_users, set(expected_users_ids)
    )
    bot = telebot.TeleBot(bot_token)
    bot.message_handler(commands=["start"], func=check_function)(
        partial(message_processing.process_start, bot)
    )
    bot.message_handler(commands=["login"], func=check_function)(
        partial(message_processing.process_login, bot)
    )
    # XXX: order of handlers matters
    bot.message_handler(content_types=["text"], func=check_function)(
        partial(message_processing.process_new_message, bot)
    )
    bot.infinity_polling()


def main():
    bot_token = os.getenv("ANKER_BOT_TOKEN")
    expected_users_ids_raw = os.getenv("ANKER_BOT_USERS")
    assert bot_token is not None
    assert expected_users_ids_raw is not None
    expected_users_ids: tuple[int] = tuple(
        map(int, expected_users_ids_raw.strip().split(","))
    )
    start_bot(bot_token=bot_token, expected_users_ids=expected_users_ids)


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    main()
