"""Skill loader: reads JSON skill configs from skills/ directory."""

import json
from pathlib import Path

import structlog

from bot.config import settings
from bot.models.agent import SkillConfig

logger = structlog.get_logger()

_SKILLS_DIR = Path(__file__).parent / "skills"

_cache: dict[str, SkillConfig] | None = None


def load_skills() -> dict[str, SkillConfig]:
    """Load all JSON skill definitions. Cached after first call."""
    global _cache
    if _cache is not None:
        return _cache

    result: dict[str, SkillConfig] = {}
    if not _SKILLS_DIR.is_dir():
        logger.warning("skills_dir_missing", path=str(_SKILLS_DIR))
        return result

    for fp in sorted(_SKILLS_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            skill = SkillConfig(**data)
            result[skill.name] = skill
            logger.debug("skill_loaded", name=skill.name)
        except Exception as e:
            logger.error("skill_load_error", file=fp.name, error=str(e))

    _cache = result
    logger.info("skills_loaded", count=len(result))
    return result


def get_skill(name: str) -> SkillConfig | None:
    """Get a single skill by name."""
    return load_skills().get(name)


def get_agent_skills(agent_skills: list[str]) -> list[SkillConfig]:
    """Resolve a list of skill names to SkillConfig objects."""
    all_skills = load_skills()
    return [all_skills[s] for s in agent_skills if s in all_skills]


def validate_skill_requirements(skill: SkillConfig) -> bool:
    """Check that all required_settings are present in config."""
    for key in skill.required_settings:
        if not getattr(settings, key, ""):
            return False
    return True
