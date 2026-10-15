"""System prompts. One file per model role."""
from app.prompts.decider import SYSTEM_PROMPT
from app.prompts.decider_sol import SOL_SYSTEM_PROMPT
from app.prompts.writer import WRITER_SYSTEM_PROMPT

__all__ = ["SOL_SYSTEM_PROMPT", "SYSTEM_PROMPT", "WRITER_SYSTEM_PROMPT"]
