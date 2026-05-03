import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from aiwardrobe_bot.keyboards import main_keyboard, result_keyboard
from aiwardrobe_core.config import get_settings

router = Router()


@router.message(Command("start"))
async def start(message: Message) -> None:
    settings = get_settings()
    await message.answer(
        "AI-гардероб поможет оцифровать вещи, собрать образы и объяснить, почему они работают.",
        reply_markup=main_keyboard(settings.miniapp_public_url),
    )


@router.message(Command("upload"))
async def upload_help(message: Message) -> None:
    await message.answer(
        "Отправьте фото вещи, лука или скриншот товара. Я поставлю обработку в очередь и пришлю результат."
    )


@router.message(Command("wardrobe"))
async def wardrobe(message: Message) -> None:
    settings = get_settings()
    await message.answer("Гардероб открывается внутри Telegram Mini App.", reply_markup=main_keyboard(settings.miniapp_public_url))


@router.message(Command("favorites"))
async def favorites(message: Message) -> None:
    settings = get_settings()
    await message.answer("Избранные луки и аутфиты доступны в Mini App.", reply_markup=main_keyboard(settings.miniapp_public_url))


@router.message(Command("delete_me"))
async def delete_me(message: Message) -> None:
    await message.answer(
        "Удаление аккаунта и данных предусмотрено архитектурой privacy-модуля. "
        "В production этот запрос должен подтверждаться повторным действием."
    )


@router.callback_query(F.data == "upload_help")
async def upload_help_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer("Пришлите фото сюда в чат или откройте Mini App для direct upload.")


@router.callback_query(F.data == "privacy_policy")
async def privacy_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Фото приватные: web research получает только текстовое описание вещи, не изображение."
        )


@router.message(F.photo)
async def photo_upload(message: Message) -> None:
    settings = get_settings()
    photo = message.photo[-1]
    await message.answer(
        f"Фото принято. file_id: {photo.file_id[:16]}... Обработка должна идти через backend queue.",
        reply_markup=result_keyboard(settings.miniapp_public_url),
    )


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required; mock Telegram mode is disabled.")
    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
