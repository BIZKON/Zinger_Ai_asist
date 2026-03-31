"""Tests for call engine components."""

from bot.call_engine.dialog_manager import CallDialogManager


def test_dialog_manager_init():
    dm = CallDialogManager(
        user_id="test-uuid",
        user_name="Сергей",
        contact_name="Иванов",
        script_type="manual",
    )
    assert dm.user_id == "test-uuid"
    assert dm.user_name == "Сергей"
    assert dm.contact_name == "Иванов"
    assert dm.messages == []
    assert dm.transcript_lines == []


def test_dialog_manager_transcript():
    dm = CallDialogManager(user_id="test", user_name="User")
    dm.transcript_lines.append("Собеседник: Алло")
    dm.transcript_lines.append("Ассистент: Здравствуйте")

    transcript = dm.get_transcript()
    assert "Алло" in transcript
    assert "Здравствуйте" in transcript


def test_dialog_manager_duration():
    dm = CallDialogManager(user_id="test", user_name="User")
    # Duration should be >= 0 immediately
    assert dm.duration_sec >= 0


def test_dialog_manager_system_prompt():
    dm = CallDialogManager(
        user_id="test",
        user_name="Сергей",
        contact_name="Иванов",
        script_type="manual",
    )
    prompt = dm._build_system_prompt()
    assert "Сергей" in prompt
    assert "Иванов" in prompt
    assert "телефонный" in prompt
