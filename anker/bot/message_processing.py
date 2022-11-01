from __future__ import annotations

import email.utils
import json
import logging
import typing as _t

import telebot

from anker import anki_api
from anker.bot.client_state import ClientState, ClientStates
from anker.card_generation import translation
from anker.types import UserInfo

logger = logging.getLogger(__name__)


GET_DECKS_BATCH_SIZE = 10


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
        case ClientStates.CREATE_NEW_DECK:
            _process_create_new_deck(bot, message, client_state, state_message_id)
        case _:
            _process_new_word(bot, message, client_state, state_message_id)


def process_callback_query(
    bot: telebot.TeleBot, callback_query: telebot.types.CallbackQuery
):
    message = callback_query.message
    chat_id = message.chat.id
    client_state, state_message_id = _get_or_create_state_message(bot, chat_id)
    match client_state.state:
        case ClientStates.SELECT_DECK:
            _process_select_deck(bot, callback_query, client_state, state_message_id)
        case ClientStates.SELECT_LANG:
            _process_select_language(
                bot, callback_query, client_state, state_message_id
            )
        case _:
            _process_select_translation(
                bot, callback_query, client_state, state_message_id
            )


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


def process_lang(bot: telebot.TeleBot, message: telebot.types.Message):
    logger.info(msg={"comment": "process language", "user": message.from_user.id})
    chat_id = message.chat.id
    (client_state, message_id) = _get_or_create_state_message(bot, chat_id)
    new_client_state = client_state.make_from(
        language_to="", language_from="", state=ClientStates.SELECT_LANG
    )
    _update_state_message_or_pin_new(bot, new_client_state, message_id, chat_id)

    bot.reply_to(
        message,
        "Select language to translate from:",
        reply_markup=_get_languages_message(),
    )


def process_decks(bot: telebot.TeleBot, message: telebot.types.Message):
    logger.info(msg={"comment": "process deck command"})
    chat_id = message.chat.id
    (client_state, state_message_id) = _get_or_create_state_message(bot, chat_id)
    if client_state.anki_user_info is None:
        bot.reply_to(message, "Please use /login first")
        return
    new_client_state = client_state.make_from(state=ClientStates.SELECT_DECK)
    _update_state_message_or_pin_new(bot, new_client_state, state_message_id, chat_id)
    (client_state, state_message_id, (decks_map, _)) = anki_call_guard(
        bot,
        chat_id,
        client_state,
        state_message_id,
        lambda: anki_api.get_decks_and_note_types(
            client_state.anki_user_info  # type: ignore
        ),
    )
    for decks_message in _get_decks_messages(decks_map):
        bot.reply_to(message, "Decks:", reply_markup=decks_message)


def process_add_deck(bot: telebot.TeleBot, message: telebot.types.Message):
    logger.info(msg={"comment": "add a deck"})
    chat_id = message.chat.id
    _set_new_client_state(bot, chat_id, ClientStates.CREATE_NEW_DECK)
    bot.reply_to(message, "Send me a name of a new deck")


def _process_select_language(
    bot: telebot.TeleBot,
    callback_query: telebot.types.CallbackQuery,
    client_state: ClientState,
    state_message_id: int,
):
    logger.info(msg={"comment": "select languages"})
    chat_id = callback_query.message.chat.id
    lang = callback_query.data
    available_languages = translation.get_available_languages()
    if lang not in available_languages:
        bot.send_message(chat_id, f"Unknown language '{lang}', please call /lang again")
        return
    if client_state.language_from == "":
        new_client_state = client_state.make_from(language_from=lang)
        _update_state_message_or_pin_new(
            bot, new_client_state, state_message_id, chat_id
        )
        bot.reply_to(
            callback_query.message,
            "Select language to translate to:",
            reply_markup=_get_languages_message(except_language=lang),
        )
        return
    new_client_state = client_state.make_from(
        language_to=lang, state=ClientStates.AUTHORIZED
    )
    _update_state_message_or_pin_new(bot, new_client_state, state_message_id, chat_id)
    bot.reply_to(
        callback_query.message,
        f"Languages are selected. From '{new_client_state.language_from}' to "
        f"'{new_client_state.language_to}'",
    )
    return


def _process_select_deck(
    bot: telebot.TeleBot,
    callback_query: telebot.types.CallbackQuery,
    client_state: ClientState,
    state_message_id: int,
):
    logger.info(msg={"comment": "select a deck"})
    chat_id = callback_query.message.chat.id
    if client_state.anki_user_info is None:
        bot.send_message(chat_id, "Please use /login first")
        return

    deck_id = callback_query.data
    (client_state, state_message_id, (decks_map, note_types)) = anki_call_guard(
        bot,
        chat_id,
        client_state,
        state_message_id,
        lambda: anki_api.get_decks_and_note_types(
            client_state.anki_user_info  # type: ignore
        ),
    )
    deck_info = next(
        filter(lambda deck: deck.deck_id == deck_id, decks_map.values()), None
    )
    if deck_info is None:
        bot.send_message(chat_id, "Deck was not found. Please, call /decks again")
        return

    expected_node_type_name = "Basic (and reversed card)"
    if expected_node_type_name not in note_types:
        bot.send_message(
            chat_id,
            f"We are expecting note type with a value '{expected_node_type_name}'. "
            "Please add it to your anki account: "
            "https://docs.ankiweb.net/editing.html#adding-a-note-type",
        )
        return
    note_type = note_types[expected_node_type_name]

    new_client_state = client_state.make_from(
        anki_deck_info=deck_info,
        state=ClientStates.AUTHORIZED,
        anki_note_type_info=note_type,
    )
    _update_state_message_or_pin_new(bot, new_client_state, state_message_id, chat_id)
    bot.send_message(chat_id, f"Deck '{deck_info.deck_name}' was selected")


def _check_state_is_ready_to_add_a_card(
    bot: telebot.TeleBot, message: telebot.types.Message, client_state: ClientState
) -> bool:
    if client_state.anki_user_info is None:
        bot.reply_to(message, "Please use /login first")
        return False
    if client_state.anki_deck_info is None or client_state.anki_note_type_info is None:
        bot.reply_to(message, "Please use /decks to select a deck")
        return False
    if client_state.language_from == "" or client_state.language_to == "":
        bot.reply_to(message, "Please use /lang to set languages")
        return False
    return True


def _process_new_word(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    client_state: ClientState,
    state_message_id: int,
):
    logger.info(msg={"comment": "process a new word"})
    possible_word = message.text.strip()
    if not _check_state_is_ready_to_add_a_card(bot, message, client_state):
        return

    translation_result = translation.get_translations(
        from_language=client_state.language_from,
        to_language=client_state.language_to,
        input_text=possible_word,
    )
    if translation_result is None or len(translation_result.possible_translations) == 0:
        bot.reply_to(message, f"Can't translate {possible_word}")
        return

    for translation_text in translation.format_translation_result_iterator(
        translation_result
    ):
        keyboard_markup = telebot.types.InlineKeyboardMarkup()
        button_markup = telebot.types.InlineKeyboardButton(
            text="add to the deck", callback_data=possible_word
        )
        keyboard_markup.add(button_markup)
        bot.send_message(
            chat_id=message.chat.id, text=translation_text, reply_markup=keyboard_markup
        )


def _process_select_translation(
    bot: telebot.TeleBot,
    callback_query: telebot.types.CallbackQuery,
    client_state: ClientState,
    state_message_id: int,
):
    logger.info(msg={"comment": "select a new translation"})
    if not _check_state_is_ready_to_add_a_card(
        bot, callback_query.message, client_state
    ):
        return
    assert client_state.anki_deck_info is not None
    assert client_state.anki_note_type_info is not None
    assert client_state.anki_user_info is not None
    chat_id = callback_query.message.chat.id

    (client_state, state_message_id, note_type_fields) = anki_call_guard(
        bot,
        chat_id,
        client_state,
        state_message_id,
        lambda: anki_api.get_note_type_fields(
            client_state.anki_user_info,  # type: ignore
            client_state.anki_note_type_info,  # type: ignore
        ),
    )
    # TODO: better check
    assert {"Front", "Back"} == set((f.field_name for f in note_type_fields))

    translation_text = callback_query.message.text
    word = callback_query.data
    new_card_info = anki_api.CardInfo(
        front_text=word,
        back_text=translation_text,
    )
    (client_state, state_message_id, _) = anki_call_guard(
        bot,
        chat_id,
        client_state,
        state_message_id,
        lambda: anki_api.add_card_to_deck(
            client_state.anki_user_info,  # type: ignore
            client_state.anki_deck_info,  # type: ignore
            client_state.anki_note_type_info,  # type: ignore
            note_type_fields,
            card_info=new_card_info,
        ),
    )
    bot.send_message(chat_id, "Added a new card!")


def _process_create_new_deck(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
    client_state: ClientState,
    state_message_id: int,
):
    logger.info(msg={"comment": "create a new deck"})
    possible_name = message.text.strip()
    if client_state.anki_user_info is None:
        bot.reply_to(message, "Please use /login first")
        return
    chat_id = message.chat.id
    (client_state, state_message_id, _) = anki_call_guard(
        bot,
        chat_id,
        client_state,
        state_message_id,
        lambda: anki_api.create_deck(
            client_state.anki_user_info, possible_name  # type: ignore
        ),
    )
    new_client_state = client_state.make_from(state=ClientStates.AUTHORIZED)
    _update_state_message_or_pin_new(bot, new_client_state, state_message_id, chat_id)
    bot.reply_to(message, "Deck is created. Use /decks to select it now")


def _set_new_client_state(bot: telebot.TeleBot, chat_id: int, new_state: ClientStates):
    (client_state, message_id) = _get_or_create_state_message(bot, chat_id)
    if client_state.state != new_state:
        new_client_state = client_state.make_from(state=new_state)
        _update_state_message_or_pin_new(bot, new_client_state, message_id, chat_id)


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


def _get_decks_messages(
    decks_info: dict[str, anki_api.DeckInfo],
) -> tuple[telebot.types.InlineKeyboardMarkup, ...]:
    decks = list(decks_info.values())
    messages = []
    for chunk_start in range(0, len(decks), GET_DECKS_BATCH_SIZE):
        chunk_end = chunk_start + GET_DECKS_BATCH_SIZE
        keyboard_markup = telebot.types.InlineKeyboardMarkup()
        for deck in decks[chunk_start:chunk_end]:
            button_markup = telebot.types.InlineKeyboardButton(
                text=deck.deck_name, callback_data=deck.deck_id
            )
            keyboard_markup.add(button_markup)
        messages.append(keyboard_markup)
    return tuple(messages)


def _get_languages_message(
    except_language: _t.Optional[str] = None,
) -> telebot.types.InlineKeyboardMarkup:
    keyboard_markup = telebot.types.InlineKeyboardMarkup()
    for lang in translation.get_available_languages():
        if lang == except_language:
            continue
        button_markup = telebot.types.InlineKeyboardButton(
            text=lang, callback_data=lang
        )
        keyboard_markup.add(button_markup)
    return keyboard_markup


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
    user_info: UserInfo
    try:
        user_info = anki_api.login(
            username=client_state.anki_user_email, password=user_password
        )
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
        anki_password=user_password,
        state=ClientStates.AUTHORIZED,
        anki_user_info=user_info,
    )
    _update_state_message_or_pin_new(
        bot, new_client_state, state_message_id, message.chat.id
    )
    if new_client_state.anki_deck_info is None:
        # TODO: put here a list of decks
        bot.send_message(
            chat_id=chat_id,
            text="All is good! You can now call `/decks` to choose a deck "
            "from a list or call `/add_deck` to add a new deck",
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


def relogin_and_update_user_info(
    bot: telebot.TeleBot,
    chat_id: int,
    client_state: ClientState,
    state_message_id: int,
) -> tuple[ClientState, int] | None:
    logger.info(
        msg={
            "comment": "relogin and update client state",
            "chat_id": chat_id
        }
    )
    user_info: UserInfo
    try:
        user_info = anki_api.login(
            username=client_state.anki_user_email, password=client_state.anki_password
        )
    except Exception:
        # TODO: make exceptions less broad
        logger.exception(msg={"comment": "can't login user to ankiweb"})
        bot.send_message(
            chat_id=chat_id,
            text="We were no able to login to anki. Please call /login again "
            "or try again",
        )
        return None
    new_client_state = client_state.make_from(anki_user_info=user_info)
    new_state_message_id = _update_state_message_or_pin_new(
        bot, new_client_state, state_message_id, chat_id
    )
    return new_client_state, new_state_message_id


T = _t.TypeVar("T")


def anki_call_guard(
    bot: telebot.TeleBot,
    chat_id: int,
    client_state: ClientState,
    state_message_id: int,
    wrapped_func: _t.Callable[[], T],
) -> tuple[ClientState, int, T]:
    maximum_number_of_retries = 5
    cached_client_state = client_state
    cached_state_message_id = state_message_id
    for _ in range(maximum_number_of_retries):
        try:
            result = wrapped_func()
            return (cached_client_state, cached_state_message_id, result)
        except anki_api.AnkiAuthorizationException:
            new_state = relogin_and_update_user_info(
                bot, chat_id, cached_client_state, cached_state_message_id
            )
            if new_state is None:
                bot.send_message(
                    chat_id=chat_id,
                    text="We were not able to relogin. Please, try again or "
                    "check the login credentials.",
                )
                raise RuntimeError("Not able to relogin user")
            (cached_client_state, cached_state_message_id) = new_state
        except Exception:
            logger.info(
                msg={
                    "comment": "We were not able to call anki function. Try one "
                    "more time"
                }
            )
            continue
    bot.send_message(chat_id=chat_id, text="We failed. Please try again!")
    raise RuntimeError(
        "Not able to call anki_api with " f"{maximum_number_of_retries} retries"
    )
