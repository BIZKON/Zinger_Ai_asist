"""Claude API + каскадный роутинг LLM.

Каскад:
  - simple (intent detection) → Gemini Flash (бесплатно)
  - medium (обычный диалог)  → Claude Haiku
  - complex (сложные задачи) → Claude Sonnet
"""

# TODO: Реализация в Фазе 1
