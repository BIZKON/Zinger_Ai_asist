"""PersonalAI Sergiy — bot entry point."""

import asyncio
import logging

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.database import close_db
from bot.handlers import (
    start, voice, media, digest, tasks, schedule,
    contacts, one_c_commands, calls, callbacks, chat,
    agents,
)
from bot.handlers import payments
from bot.orchestration import heartbeat
from bot.middleware.rate_limit import RateLimitMiddleware

logger = structlog.get_logger()


def setup_sentry() -> None:
    """Initialize Sentry error monitoring."""
    if not settings.sentry_dsn:
        return

    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1 if settings.is_production else 1.0,
        )
        logger.info("sentry_initialized")
    except ImportError:
        logger.warning("sentry_sdk_not_installed")
    except Exception as e:
        logger.warning("sentry_init_error", error=str(e))


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(message)s",
    )

    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if settings.is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


async def main() -> None:
    # Initialize monitoring first
    setup_sentry()
    setup_logging()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Rate limiting middleware
    dp.message.middleware(RateLimitMiddleware())

    # Register routers (order matters — first match wins)
    dp.include_router(start.router)         # /start, /help, onboarding FSM
    dp.include_router(digest.router)        # /digest
    dp.include_router(tasks.router)         # /tasks, /task, /done
    dp.include_router(schedule.router)      # /search, /research, /events, /remind
    dp.include_router(payments.router)      # /subscribe, /billing
    dp.include_router(contacts.router)      # /contacts, /contact
    dp.include_router(one_c_commands.router) # /waybills, /waybill, /orders
    dp.include_router(calls.router)         # /call, /calls
    dp.include_router(agents.router)        # /agents, /goals, /agent_cost
    dp.include_router(callbacks.router)     # inline button callbacks
    dp.include_router(media.router)         # photos, documents, files
    dp.include_router(voice.router)         # voice/audio messages
    dp.include_router(chat.router)          # text messages (catch-all, must be last)

    logger.info("starting_bot", environment=settings.environment)

    # Start Agent Orchestration heartbeat
    await heartbeat.start(bot)

    try:
        if settings.is_production and settings.webhook_url:
            # Webhook mode for production
            from aiogram.webhook.aiohttp_server import (
                SimpleRequestHandler,
                setup_application,
            )
            from aiohttp import web

            await bot.set_webhook(settings.webhook_url)
            app = web.Application()
            handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
            handler.register(app, path="/webhook")
            setup_application(app, dp, bot=bot)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", 8080)
            await site.start()
            logger.info("webhook_started", url=settings.webhook_url)
            await asyncio.Event().wait()
        else:
            # Polling mode for development
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
    finally:
        await heartbeat.stop()
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
