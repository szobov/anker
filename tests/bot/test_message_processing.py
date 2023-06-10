from unittest.mock import MagicMock, patch

from telebot.types import Chat, Message
import responses

from anker.bot.message_processing import process_start


def test_process_start(
    mocked_telebot: MagicMock, mocked_http_requests: responses.RequestsMock
):
    chat_dict = {"id": 1, "type": "private"}
    user_dict = {
        "id": 24,
        "is_bot": False,
        "first_name": "test user",
    }
    incomming_message = Message.de_json(
        {
            "message_id": 122,
            "date": 1111,
            "chat": chat_dict,
            "from": user_dict,
        }
    )
    incomming_message.chat.id = 42

    pinned_message = Message.de_json(
        {"message_id": 24, "date": 11, "chat": chat_dict, "text": ""}
    )
    pinned_message.chat.id = 42

    state_message = Message.de_json({"message_id": 124, "date": 111, "chat": chat_dict})

    mocked_telebot.get_chat.return_value = Chat(
        1, "private", pinned_message=pinned_message
    )
    mocked_telebot.send_message.return_value = state_message

    mocked_file_url = "https://telegram.org/files?id=123"
    mocked_telebot.get_file_url.return_value = mocked_file_url

    mocked_http_requests.get(
        mocked_file_url,
        body="",
        status=200,
        content_type="text/html",
    )

    with patch("telebot.apihelper._make_request") as mocked_make_handler:
        process_start(mocked_telebot, incomming_message)
        mocked_make_handler.assert_called_once()
    mocked_telebot.reply_to.assert_called_once()
    mocked_telebot.unpin_chat_message.assert_called_once_with(
        42, pinned_message.message_id
    )
    mocked_telebot.pin_chat_message.assert_called_once_with(
        chat_id=42, message_id=state_message.message_id, disable_notification=True
    )
