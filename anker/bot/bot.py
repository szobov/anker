from __future__ import annotations

import logging
import os
from functools import partial

import telebot

from anker.bot import message_processing

logger = logging.getLogger(__name__)


def _check_message_type_and_expected_users(
    expected_users: set[int],
    message_or_callback_query: telebot.types.Message | telebot.types.CallbackQuery,
) -> bool:
    chat_type: str
    user_id: int
    if isinstance(message_or_callback_query, telebot.types.CallbackQuery):
        if message_or_callback_query.message is None:
            return False
        chat_type = message_or_callback_query.message.chat.type
        user_id = message_or_callback_query.from_user.id
    else:
        chat_type = message_or_callback_query.chat.type
        user_id = message_or_callback_query.from_user.id
    logger.debug(
        msg={
            "comment": "check message type and user",
            "user_id": user_id,
            "message_type": chat_type,
        }
    )
    if chat_type != "private":
        return False
    if len(expected_users) == 0:
        return True
    if user_id in expected_users:
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
    bot.message_handler(commands=["add_deck"], func=check_function)(
        partial(message_processing.process_add_deck, bot)
    )
    bot.message_handler(commands=["decks"], func=check_function)(
        partial(message_processing.process_decks, bot)
    )
    bot.message_handler(commands=["lang"], func=check_function)(
        partial(message_processing.process_lang, bot)
    )
    bot.callback_query_handler(func=check_function)(
        partial(message_processing.process_callback_query, bot)
    )
    # XXX: order of handlers matters
    bot.message_handler(content_types=["text"], func=check_function)(
        partial(message_processing.process_new_message, bot)
    )
    bot.infinity_polling(logger_level=None)


def main():
    bot_token = os.getenv("ANKER_BOT_TOKEN")
    expected_users_ids_raw = os.getenv("ANKER_BOT_USERS")
    assert bot_token is not None
    assert expected_users_ids_raw is not None
    expected_users_ids_raw = expected_users_ids_raw.strip()
    if expected_users_ids_raw == "":
        expected_users_ids = ()
    else:
        expected_users_ids: tuple[int] = tuple(
            map(int, expected_users_ids_raw.split(","))
        )
    start_bot(bot_token=bot_token, expected_users_ids=expected_users_ids)


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    main()
