from __future__ import annotations

import email.utils
import json
import logging

import telebot

from anker import anki_api
from anker.bot.client_state import ClientState, ClientStates

logger = logging.getLogger(__name__)


def process_new_message(bot: telebot.TeleBot, message: telebot.types.Message):
    chat_id = message.chat.id
    client_state, state_message_id = _get_or_create_state_message(bot, chat_id)
    match client_state.state:
        case ClientStates.UNAUTHORIZED:
            bot.reply_to(message, "Use /login first to let bot access anki")
        case ClientStates.SET_USER_EMAIL:
            _process_set_user_email(bot, message, client_state, state_message_id)
        case ClientStates.SET_PASSWORD:
            _process_set_password(bot, message, client_state, state_message_id)


def process_start(bot: telebot.TeleBot, message: telebot.types.Message):
    logger.info(msg={"comment": "process authentication", "message": message})
    bot.reply_to(
        message,
        """
Hey,
First, you need to send me a login and password for your [anki](https://ankiweb.net/)
account using `/login <email> <password`. The password will be not stored on the bot's
server, it will be obscured and then stored in the pinned message in this chat.
I'll also pin a message with technical information for the bot. It's required and
*must not* be unpinned.
""",
    )
    _get_or_create_state_message(bot, message.chat.id)


def process_login(bot: telebot.TeleBot, message: telebot.types.Message):
    logger.debug(
        msg={"comment": "process authentication", "user": message.from_user.id}
    )
    chat_id = message.chat.id
    (client_state, message_id) = _get_or_create_state_message(bot, chat_id)
    if client_state.state != ClientStates.SET_USER_EMAIL:
        new_client_state = client_state.make_from(state=ClientStates.SET_USER_EMAIL)
        _update_state_message_or_pin_new(bot, new_client_state, message_id, chat_id)
    bot.reply_to(message, "Send me an email")


def _get_pinned_message_id_and_text(
    bot: telebot.TeleBot, chat_id: int
) -> tuple[int, str] | None:
    message = bot.get_chat(chat_id=chat_id).pinned_message
    if message is None:
        return None
    return message.message_id, message.text


def _update_state_message_or_pin_new(
    bot: telebot.TeleBot, state: ClientState, message_id: int, chat_id: int
) -> int:
    try:
        bot.edit_message_text(
            json.dumps(state.get_encrypted()), chat_id=chat_id, message_id=message_id
        )
        return message_id
    except telebot.apihelper.ApiTelegramException as ex:
        if ex.error_code == 400:
            bot.unpin_chat_message(chat_id, message_id)
        return _create_state_message(bot, chat_id, state)


def _process_set_password(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    client_state: ClientState,
    state_message_id: int,
):
    user_password = message.text.strip()
    chat_id = message.chat.id
    bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    if client_state.anki_user_email == "":
        new_client_state = client_state.make_from(state=ClientStates.SET_USER_EMAIL)
        _update_state_message_or_pin_new(
            bot, new_client_state, state_message_id, chat_id
        )
        bot.send_message(chat_id=chat_id, text="Please send email first")
        return
    if len(user_password) == 0:
        bot.send_message(
            chat_id=chat_id,
            text="No passwords seems to be found. Could you please send it again?",
        )
        return
    try:
        anki_api.login(username=client_state.anki_user_email, password=user_password)
    except Exception:
        # TODO: make exceptions less broad
        logger.exception(msg={"comment": "can't login user to ankiweb"})
        bot.send_message(
            chat_id=chat_id,
            text="We were no able to login with such password. Please send us a new "
            "passwords or call /login again",
        )
        return
    new_client_state = client_state.make_from(
        anki_password=user_password, state=ClientStates.AUTHORIZED
    )
    _update_state_message_or_pin_new(
        bot, new_client_state, state_message_id, message.chat.id
    )
    if new_client_state.deck_id == "":
        # TODO: put here a list of decks
        bot.send_message(
            chat_id=chat_id,
            text="All is good! You can now choose a deck from the list: ",
        )
        return
    if new_client_state.language_from == "" or new_client_state.language_to == "":
        bot.send_message(
            chat_id=chat_id,
            text="All is good! You can now choose the languages by clicking /lang",
        )
        return

    bot.send_message(
        chat_id=chat_id, text="All is good! Send me a word to make a card from now."
    )


def _process_set_user_email(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    client_state: ClientState,
    state_message_id: int,
):
    (_, user_email) = email.utils.parseaddr(message.text)
    if user_email == "":
        bot.reply_to(
            message, "The email seems to be misspelled. Could you please send it again?"
        )
        return
    new_client_state = client_state.make_from(
        anki_user_email=user_email, state=ClientStates.SET_PASSWORD
    )
    _update_state_message_or_pin_new(
        bot, new_client_state, state_message_id, message.chat.id
    )
    bot.reply_to(message, "Send me a password (it won't be store on the server)")


def _create_state_message(
    bot: telebot.TeleBot, chat_id: int, state: ClientState
) -> int:
    state_message = bot.send_message(chat_id, json.dumps(state.get_encrypted()))

    bot.pin_chat_message(
        chat_id=chat_id,
        message_id=state_message.message_id,
        disable_notification=True,
    )
    return state_message.message_id


def _get_or_create_state_message(
    bot: telebot.TeleBot, chat_id: int
) -> tuple[ClientState, int]:
    existing_state_message = _get_pinned_message_id_and_text(bot, chat_id)
    state = None
    if existing_state_message is not None:
        message_id, text = existing_state_message
        try:
            state = ClientState.from_encrypted(json.loads(text))
        except json.JSONDecodeError:
            ...
        if state is None:
            bot.unpin_chat_message(chat_id, message_id)
    if state is not None:
        return state, message_id
    new_state = ClientState.identity()
    new_state_message_id = _create_state_message(bot, chat_id, new_state)
    return new_state, new_state_message_id
