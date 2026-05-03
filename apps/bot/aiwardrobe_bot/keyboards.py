from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def main_keyboard(miniapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть гардероб",
                    web_app=WebAppInfo(url=miniapp_url),
                )
            ],
            [InlineKeyboardButton(text="Загрузить фото", callback_data="upload_help")],
            [InlineKeyboardButton(text="Privacy policy", callback_data="privacy_policy")],
        ]
    )


def result_keyboard(miniapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть результат", web_app=WebAppInfo(url=miniapp_url))]
        ]
    )
