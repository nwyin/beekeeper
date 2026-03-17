"""Obsidian writer: appends Beekeeper section to daily notes."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_VAULT_PATH = Path.home() / "notes"
DAILIES_SUBDIR = "dailies"
SECTION_HEADER = "## Beekeeper"

DAILY_TEMPLATE = """\
---
date: {date}
tags: [daily]
---
"""


def _daily_note_path(vault_path: Path, date: str) -> Path:
    return vault_path / DAILIES_SUBDIR / f"{date}.md"


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def write_daily_note(
    markdown: str,
    vault_path: Path | None = None,
    date: str | None = None,
) -> Path:
    if vault_path is None:
        vault_path = DEFAULT_VAULT_PATH
    if date is None:
        date = _today()

    note_path = _daily_note_path(vault_path, date)
    note_path.parent.mkdir(parents=True, exist_ok=True)

    if note_path.exists():
        content = note_path.read_text()
    else:
        content = DAILY_TEMPLATE.format(date=date)
        logger.info("Creating new daily note: %s", note_path)

    # Idempotent: replace existing Beekeeper section
    pattern = re.compile(
        r"^## Beekeeper\n.*?(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )

    if pattern.search(content):
        content = pattern.sub(markdown, content)
        logger.info("Replaced existing Beekeeper section in %s", note_path)
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        content += "\n" + markdown
        logger.info("Appended Beekeeper section to %s", note_path)

    note_path.write_text(content)
    return note_path
