"""Handler: /start and /help commands."""

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

router = Router()

GREETING = (
    "Привет, <b>{name}</b>. Я — Сергий, твой персональный ИИ-ассистент.\n\n"
    "Ироничный, по делу, без воды. Расскажи мне о себе — "
    "или просто спроси что-нибудь.\n\n"
    "Команды:\n"
    "/start — начать сначала\n"
    "/help — справка"
)

HELP_TEXT = (
    "<b>Что я умею:</b>\n\n"
    "💬 Отвечаю на вопросы (текст и голосовые)\n"
    "📋 Управляю задачами\n"
    "📊 Показываю данные из 1С\n"
    "📞 Звоню контрагентам\n"
    "📄 Распознаю документы и фото\n"
    "🔍 Ищу информацию в интернете\n\n"
    "Просто напиши мне — разберёмся."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    name = message.from_user.first_name or "друг"
    await message.answer(GREETING.format(name=name))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)
