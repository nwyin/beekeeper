"""LLM client for generating PM analysis of scout reports."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import anthropic

from beekeeper.paths import DEFAULT_REGISTRY_PATH

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_MODEL = "claude-opus-4-6"
MAX_TOKENS = 4096


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text().strip()


def generate_analysis(reports: list[dict], registry_context: str | None = None, memory_context: str | None = None) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping LLM analysis")
        return None

    model = os.environ.get("BEEKEEPER_LLM_MODEL", DEFAULT_MODEL)

    system_prompt = _load_prompt("pm-system")
    user_template = _load_prompt("pm-user")
    user_content = user_template.format(
        reports=json.dumps(reports, indent=2),
        registry=registry_context or "",
        memory=memory_context or "(No PM memory file found.)",
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        content = message.content[0].text
        return content.strip() or None
    except (anthropic.APIError, IndexError) as e:
        logger.error("LLM analysis failed: %s", e)
        return None


def load_registry_text(registry_path: Path | None = None) -> str:
    if registry_path is None:
        registry_path = DEFAULT_REGISTRY_PATH
    try:
        return registry_path.read_text()
    except OSError:
        return ""
