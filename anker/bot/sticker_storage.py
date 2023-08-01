import io
import json
import typing as _t
import logging

import PIL
import qrcode
import requests
import telebot
from pyzbar import pyzbar


logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT = 5 * 60

DEFAULT_STICKER_EMOJI = "🤖"
DEFAULT_STICKER_SET_TITLE = "test"


def _create_qr_code_image_from_data(data: _t.Any) -> io.BytesIO:
    qr = qrcode.make(json.dumps(data))
    image = qr.get_image().resize((512, 512))

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="PNG")
    return img_byte_arr


def _extract_data_from_qr_code_image(image: PIL.Image) -> _t.Any | None:
    try:
        decoded = pyzbar.decode(image)[0].data
    except pyzbar.PyZbarError as ex:
        logger.debug(msg={"comment": "Can't decode qr code data", "exception": str(ex)})
        return None
    try:
        return json.loads(decoded)
    except json.JSONDecodeError as ex:
        logger.debug(
            msg={"comment": "Can't decode json from qr code data", "exception": str(ex)}
        )
        return None


def make_sticker_set_name_for_user(user_id: int, bot_name: str) -> str:
    return f"user_{user_id}_by_{bot_name}"


def get_sticker_set(
    bot: telebot.TeleBot, sticker_set_name: str
) -> telebot.types.StickerSet | None:
    try:
        return bot.get_sticker_set(sticker_set_name)
    except telebot.apihelper.ApiTelegramException:
        return None


def remove_sticker_set(bot: telebot.TeleBot, sticker_set_name: str) -> None:
    try:
        telebot.apihelper._make_request(
            bot.token,
            "deleteStickerSet",
            params={"name": sticker_set_name},
            method="POST",
        )
    except telebot.apihelper.ApiTelegramException as ex:
        logger.debug(
            msg={
                "comment": "Can't remove sticker set",
                "exception": str(ex),
                "sticker_set_name": sticker_set_name,
            }
        )


def upload_sticker_set(
    bot: telebot.TeleBot,
    user_id: int,
    sticker_set_name: telebot.types.StickerSet,
    image_data: io.BytesIO,
) -> bool:
    logger.debug(
        msg={
            "comment": "upload sticker set",
            "sticker_set_name": sticker_set_name,
            "user_id": user_id,
        }
    )
    uploaded_sticker_file = bot.upload_sticker_file(
        user_id=user_id, png_sticker=image_data.getvalue()
    )

    return bot.create_new_sticker_set(
        user_id=user_id,
        title=DEFAULT_STICKER_SET_TITLE,
        name=sticker_set_name,
        png_sticker=uploaded_sticker_file.file_id,
        emojis=[DEFAULT_STICKER_EMOJI],
    )


def extract_data_from_sticker_set(
    bot: telebot.TeleBot, sticker_set: telebot.types.StickerSet
) -> _t.Any | None:
    logger.debug(
        msg={"comment": "extract data from sticker set", "sticker_set": sticker_set}
    )
    sticker = sticker_set.stickers[0]
    sticker_data = requests.get(
        bot.get_file_url(sticker.file_id), timeout=DEFAULT_REQUEST_TIMEOUT
    )
    try:
        sticker_image = PIL.Image.open(io.BytesIO(sticker_data.content))
        return _extract_data_from_qr_code_image(sticker_image)
    except PIL.UnidentifiedImageError as ex:
        logger.debug(
            msg={
                "comment": "Can't get an image from sticker data",
                "exception": str(ex),
            }
        )
        return None


def upsert_data_in_sticker_set(
    bot: telebot.TeleBot, user_id: int, data: _t.Any
) -> None:
    logger.debug(msg={"comment": "upsert data in sticker set", "user_id": user_id})
    sticker_set_name = make_sticker_set_name_for_user(user_id, bot.get_me().username)
    existing_sticker_set = get_sticker_set(bot, sticker_set_name)
    if existing_sticker_set is not None:
        remove_sticker_set(bot, sticker_set_name)
    image_data = _create_qr_code_image_from_data(data)
    upload_sticker_set(bot, user_id, sticker_set_name, image_data)
    logger.debug(
        msg={
            "comment": "upserted data in sticker set",
            "user_id": user_id,
            "stiker_set_name": sticker_set_name,
        }
    )


def get_data_from_sticker_set_for_user(bot: telebot.TeleBot, user_id: int) -> _t.Any:
    sticker_set_name = make_sticker_set_name_for_user(user_id, bot.get_me().username)
    sticker_set = get_sticker_set(bot, sticker_set_name)
    if sticker_set is None:
        return None
    return extract_data_from_sticker_set(bot, sticker_set)
