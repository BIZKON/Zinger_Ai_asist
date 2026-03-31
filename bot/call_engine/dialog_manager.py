"""Claude диалог во время звонка — управление контекстом.

Поддерживает историю звонка и генерирует ответы в реальном времени.
"""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
import structlog

from bot.config import settings
from bot.services import llm
from bot.services.persona import build_system_prompt

logger = structlog.get_logger()


class CallDialogManager:
    """Manages conversational context during a phone call."""

    def __init__(
        self,
        user_id: str,
        user_name: str = "",
        persona_key: str = "sergiy",
        contact_name: str = "",
        script_type: str = "manual",
        script_context: str = "",
    ):
        self.user_id = user_id
        self.user_name = user_name
        self.persona_key = persona_key
        self.contact_name = contact_name
        self.script_type = script_type
        self.script_context = script_context

        self.messages: list[dict] = []
        self.transcript_lines: list[str] = []
        self.started_at = datetime.now(timezone.utc)

    def _build_system_prompt(self) -> str:
        """Build system prompt for the call context."""
        context_parts = [
            f"Ты ведёшь телефонный разговор от имени {self.user_name}.",
            f"Собеседник: {self.contact_name or 'неизвестный'}.",
            f"Тип звонка: {self.script_type}.",
        ]

        if self.script_context:
            context_parts.append(f"Контекст:\n{self.script_context}")

        context_parts.extend([
            "",
            "Правила телефонного разговора:",
            "- Говори кратко, 1-2 предложения за раз.",
            "- Будь вежлив но деловит.",
            "- Цель: получить нужную информацию или подтверждение.",
            "- Если собеседник не понял — перефразируй проще.",
            "- Завершай звонок когда цель достигнута.",
        ])

        return build_system_prompt(
            persona_key=self.persona_key,
            mood="business",
            user_name=self.user_name,
            context="\n".join(context_parts),
        )

    async def process_utterance(self, speaker_text: str) -> str:
        """Process what the other person said and generate a response.

        Args:
            speaker_text: Transcribed text from the call counterpart.

        Returns:
            AI response text to be spoken via TTS.
        """
        # Record transcript
        self.transcript_lines.append(f"Собеседник: {speaker_text}")
        self.messages.append({"role": "user", "content": speaker_text})

        # Generate response
        system = self._build_system_prompt()
        reply = await llm.chat(
            messages=self.messages,
            system_prompt=system,
            complexity="medium",
            max_tokens=150,  # Short replies for calls
        )

        self.transcript_lines.append(f"Ассистент: {reply}")
        self.messages.append({"role": "assistant", "content": reply})

        return reply

    async def get_greeting(self) -> str:
        """Generate opening greeting for outbound call."""
        greeting_prompt = (
            f"Ты звонишь {self.contact_name or 'собеседнику'} "
            f"от имени {self.user_name}. "
            f"Поздоровайся и объясни цель звонка."
        )

        if self.script_context:
            greeting_prompt += f"\nКонтекст: {self.script_context}"

        system = self._build_system_prompt()
        reply = await llm.chat(
            messages=[{"role": "user", "content": greeting_prompt}],
            system_prompt=system,
            complexity="medium",
            max_tokens=100,
        )

        self.transcript_lines.append(f"Ассистент: {reply}")
        self.messages.append({"role": "assistant", "content": reply})

        return reply

    async def summarize(self) -> str:
        """Generate a summary of the call."""
        if not self.transcript_lines:
            return "Пустой звонок."

        transcript = "\n".join(self.transcript_lines)
        prompt = (
            "Составь краткое резюме этого телефонного разговора "
            "(2-3 предложения). Укажи итог: что решено, что нужно сделать.\n\n"
            f"{transcript}"
        )

        summary = await llm.chat(
            messages=[{"role": "user", "content": prompt}],
            complexity="medium",
            max_tokens=200,
        )
        return summary

    def get_transcript(self) -> str:
        """Get full transcript text."""
        return "\n".join(self.transcript_lines)

    @property
    def duration_sec(self) -> int:
        """Call duration in seconds."""
        return int((datetime.now(timezone.utc) - self.started_at).total_seconds())

    async def save_session(
        self,
        conn: asyncpg.Connection,
        direction: str = "outbound",
        contact_phone: str = "",
        outcome: str = "",
    ) -> str:
        """Save call session to database. Returns session ID."""
        summary = await self.summarize()

        row = await conn.fetchrow(
            """
            INSERT INTO call_sessions
                (user_id, direction, contact_phone, contact_name,
                 script_type, transcript, summary, outcome, duration_sec)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
            """,
            self.user_id,
            direction,
            contact_phone,
            self.contact_name,
            self.script_type,
            self.get_transcript(),
            summary,
            outcome,
            self.duration_sec,
        )

        session_id = str(row["id"])
        logger.info(
            "call_session_saved",
            session_id=session_id,
            duration_sec=self.duration_sec,
        )
        return session_id
