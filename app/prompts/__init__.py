"""The decider's system prompt, and the block the Explain toggle adds after it."""
from app.prompts.decider import SYSTEM_PROMPT
from app.prompts.explain import EXPLAIN_BLOCK

__all__ = ["SYSTEM_PROMPT", "EXPLAIN_BLOCK"]
