"""Tests for voice TTS service."""

from bot.services.voice_tts import VOICE_MAP


def test_voice_map_has_default():
    assert "Maxim" in VOICE_MAP


def test_voice_map_all_voices():
    expected = ["Maxim", "Ivan", "Stanislav", "Elena"]
    for voice in expected:
        assert voice in VOICE_MAP, f"Missing voice: {voice}"
