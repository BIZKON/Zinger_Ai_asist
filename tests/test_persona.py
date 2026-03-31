"""Tests for persona service."""

from bot.services.persona import (
    PERSONAS,
    build_system_prompt,
    detect_mood,
    get_persona,
)


def test_get_persona_default():
    p = get_persona("sergiy")
    assert p["name"] == "Сергий"
    assert "ироничный" in p["prompt"].lower()


def test_get_persona_fallback():
    p = get_persona("nonexistent")
    assert p["name"] == "Сергий"  # fallback


def test_all_personas_have_required_keys():
    for key, persona in PERSONAS.items():
        assert "name" in persona, f"{key} missing name"
        assert "prompt" in persona, f"{key} missing prompt"
        assert "voice_id" in persona, f"{key} missing voice_id"


def test_detect_mood_urgent():
    assert detect_mood("Срочно нужна накладная!") == "urgent"


def test_detect_mood_stressed():
    assert detect_mood("Ошибка в системе") == "stressed"


def test_detect_mood_positive():
    assert detect_mood("Спасибо, класс!") == "positive"


def test_detect_mood_business():
    assert detect_mood("Покажи статус накладной") == "business"


def test_detect_mood_neutral():
    assert detect_mood("Привет") == "neutral"


def test_build_system_prompt_basic():
    prompt = build_system_prompt(persona_key="sergiy")
    assert "Сергий" in prompt
    assert "Отвечай кратко" in prompt


def test_build_system_prompt_with_user():
    prompt = build_system_prompt(
        persona_key="sergiy",
        user_name="Сергей",
        user_facts="[family]\n  жена: Анна",
    )
    assert "Сергей" in prompt
    assert "Анна" in prompt


def test_build_system_prompt_with_mood():
    prompt = build_system_prompt(persona_key="sergiy", mood="urgent")
    assert "срочная" in prompt.lower()
