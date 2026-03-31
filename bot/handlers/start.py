"""Handler: /start, онбординг FSM-визард."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

import asyncpg
import structlog

from bot.config import settings
from bot.services.memory import save_fact

logger = structlog.get_logger()

router = Router()


class Onboarding(StatesGroup):
    name = State()
    city = State()
    family = State()
    auto = State()
    sport = State()


GREETING = (
    "Привет. Я — Сергий, твой персональный ИИ-ассистент.\n\n"
    "Ироничный, по делу, без воды. Давай познакомимся — "
    "так я смогу быть полезнее.\n\n"
    "Как тебя зовут?"
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


async def _ensure_user(telegram_id: int, name: str | None = None) -> str | None:
    """Create user record if not exists. Returns user UUID."""
    try:
        conn = await asyncpg.connect(settings.database_url_raw)
        try:
            row = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_id = $1", telegram_id
            )
            if row:
                return str(row["id"])

            row = await conn.fetchrow(
                "INSERT INTO users (telegram_id, name) VALUES ($1, $2) "
                "RETURNING id",
                telegram_id, name,
            )
            logger.info("user_created", telegram_id=telegram_id)
            return str(row["id"])
        finally:
            await conn.close()
    except Exception as e:
        logger.error("user_create_error", error=str(e))
        return None


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(GREETING)
    await state.set_state(Onboarding.name)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Onboarding.name)
async def process_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip() if message.text else message.from_user.first_name
    await state.update_data(name=name)

    user_id = await _ensure_user(message.from_user.id, name)
    if user_id:
        await state.update_data(user_id=user_id)

    await message.answer(
        f"Приятно, <b>{name}</b>. В каком городе живёшь?\n"
        "(или отправь /skip если Санкт-Петербург)"
    )
    await state.set_state(Onboarding.city)


@router.message(Onboarding.city)
async def process_city(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""

    if text.startswith("/skip") or not text:
        city = "Санкт-Петербург"
    else:
        city = text

    await state.update_data(city=city)

    data = await state.get_data()
    user_id = data.get("user_id")

    if user_id:
        try:
            conn = await asyncpg.connect(settings.database_url_raw)
            try:
                await conn.execute(
                    "UPDATE users SET city = $1 WHERE id = $2::uuid",
                    city, user_id,
                )
            finally:
                await conn.close()
        except Exception as e:
            logger.warning("city_update_error", error=str(e))

    await message.answer(
        "Расскажи про семью — кто есть? (супруга, дети, их имена и возраст)\n"
        "Или /skip если пока не хочешь."
    )
    await state.set_state(Onboarding.family)


@router.message(Onboarding.family)
async def process_family(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    data = await state.get_data()
    user_id = data.get("user_id")

    if user_id and text and not text.startswith("/skip"):
        try:
            conn = await asyncpg.connect(settings.database_url_raw)
            try:
                await save_fact(conn, user_id, "family", "описание", text)
            finally:
                await conn.close()
        except Exception as e:
            logger.warning("family_save_error", error=str(e))

    await message.answer(
        "Какая у тебя машина? (марка, модель, год)\n"
        "Или /skip."
    )
    await state.set_state(Onboarding.auto)


@router.message(Onboarding.auto)
async def process_auto(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    data = await state.get_data()
    user_id = data.get("user_id")

    if user_id and text and not text.startswith("/skip"):
        try:
            conn = await asyncpg.connect(settings.database_url_raw)
            try:
                await save_fact(conn, user_id, "auto", "автомобиль", text)
            finally:
                await conn.close()
        except Exception as e:
            logger.warning("auto_save_error", error=str(e))

    await message.answer(
        "Занимаешься спортом? Каким?\n"
        "Или /skip."
    )
    await state.set_state(Onboarding.sport)


@router.message(Onboarding.sport)
async def process_sport(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    data = await state.get_data()
    user_id = data.get("user_id")

    if user_id and text and not text.startswith("/skip"):
        try:
            conn = await asyncpg.connect(settings.database_url_raw)
            try:
                await save_fact(conn, user_id, "sport", "вид_спорта", text)
            finally:
                await conn.close()
        except Exception as e:
            logger.warning("sport_save_error", error=str(e))

    name = data.get("name", "друг")
    await message.answer(
        f"Готово, <b>{name}</b>. Я тебя запомнил.\n\n"
        "Теперь просто пиши мне — текстом или голосовым. "
        "Я всегда на связи.\n\n"
        "/help — что я умею"
    )
    await state.clear()
