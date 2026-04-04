"""Tests for agent orchestration layer."""

import json
from pathlib import Path

from bot.models.agent import SkillConfig, AgentConfig, AgentTask, CostEntry
from bot.orchestration.cost_monitor import calculate_cost, PRICE_PER_1K
from bot.orchestration.skills import load_skills, get_agent_skills, validate_skill_requirements


# ── Skill loading ──

def test_load_skills_returns_dict():
    """All 7 JSON skill files should be loaded."""
    # Reset cache
    import bot.orchestration.skills as mod
    mod._cache = None

    skills = load_skills()
    assert isinstance(skills, dict)
    assert len(skills) >= 7


def test_skill_json_validity():
    """Each JSON file should parse into a valid SkillConfig."""
    skills_dir = Path(__file__).parent.parent / "bot" / "orchestration" / "skills"
    for fp in skills_dir.glob("*.json"):
        data = json.loads(fp.read_text())
        skill = SkillConfig(**data)
        assert skill.name
        assert skill.display_name


def test_get_agent_skills():
    """get_agent_skills should resolve valid names and skip invalid ones."""
    import bot.orchestration.skills as mod
    mod._cache = None

    result = get_agent_skills(["1c_odata", "nonexistent_skill"])
    assert len(result) == 1
    assert result[0].name == "1c_odata"


def test_validate_skill_requirements_missing():
    """Should return False if required settings are empty."""
    skill = SkillConfig(
        name="test",
        display_name="Test",
        required_settings=["nonexistent_setting_xyz"],
    )
    assert validate_skill_requirements(skill) is False


def test_validate_skill_no_requirements():
    """Should return True if no requirements."""
    skill = SkillConfig(name="test", display_name="Test")
    assert validate_skill_requirements(skill) is True


# ── Cost calculations ──

def test_calculate_cost_gpt4o():
    cost = calculate_cost("gpt-4o", 1000, 500)
    expected = 1000 / 1000 * 0.0025 + 500 / 1000 * 0.01
    assert abs(cost - expected) < 1e-8


def test_calculate_cost_gemini_free():
    cost = calculate_cost("gemini-flash", 10000, 5000)
    assert cost == 0.0


def test_calculate_cost_unknown_model():
    """Unknown model should use default pricing."""
    cost = calculate_cost("unknown-model", 1000, 1000)
    assert cost > 0


# ── Pydantic models ──

def test_agent_config_model():
    cfg = AgentConfig(
        id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        slug="test_agent",
        display_name="Test Agent",
    )
    assert cfg.slug == "test_agent"
    assert cfg.role == "worker"
    assert cfg.is_active is True


def test_agent_task_model():
    task = AgentTask(
        id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        agent_id="00000000-0000-0000-0000-000000000003",
        title="Test task",
    )
    assert task.status == "pending"
    assert task.priority == "medium"
    assert task.retry_count == 0


def test_cost_entry_model():
    from datetime import date
    entry = CostEntry(
        user_id="00000000-0000-0000-0000-000000000001",
        agent_id="00000000-0000-0000-0000-000000000002",
        date=date.today(),
        model="gpt-4o",
        input_tokens=500,
        output_tokens=200,
    )
    assert entry.cost_usd == 0.0
    assert entry.call_count == 0


# ── Approval callback parsing ──

def test_approval_callback_data_format():
    """Verify callback data format matches expected pattern."""
    from bot.orchestration.approval import _approval_keyboard

    task_id = "00000000-0000-0000-0000-000000000001"
    kb = _approval_keyboard(task_id)

    buttons = [btn for row in kb.inline_keyboard for btn in row]
    data_values = [btn.callback_data for btn in buttons]

    assert f"agent_approve:{task_id}" in data_values
    assert f"agent_reject:{task_id}" in data_values
    assert f"agent_info:{task_id}" in data_values
