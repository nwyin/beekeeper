"""Memory system for PM context that persists across runs."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from beekeeper.paths import DEFAULT_MEMORY_PATH


def load_memory(memory_path: Path | None = None) -> str:
    if memory_path is None:
        memory_path = DEFAULT_MEMORY_PATH
    try:
        return memory_path.read_text().strip()
    except OSError:
        return ""


def append_memo(text: str, project: str | None = None, memory_path: Path | None = None) -> Path:
    """Append a timestamped memo to memory.md under the appropriate section."""
    if memory_path is None:
        memory_path = DEFAULT_MEMORY_PATH

    timestamp = datetime.now().strftime("%Y-%m-%d")
    entry = f"- [{timestamp}] {text}\n"

    content = memory_path.read_text() if memory_path.exists() else _scaffold()

    if project:
        content = _append_to_project(content, project, entry)
    else:
        content = _append_to_section(content, "Current Focus", entry)

    memory_path.write_text(content)
    return memory_path


def _scaffold() -> str:
    return "# Strategic Goals\n\n# Current Focus\n\n# Project Notes\n\n# Decisions\n\n"


def _append_to_section(content: str, section: str, entry: str) -> str:
    """Append entry after the section header and any comment block."""
    pattern = rf"(# {re.escape(section)}\n)"
    match = re.search(pattern, content)
    if not match:
        # Section missing — add it at the end
        return content.rstrip() + f"\n\n# {section}\n\n{entry}"

    # Find insertion point: after header + any blank lines + any HTML comments
    insert_pos = match.end()
    remaining = content[insert_pos:]

    # Skip blank lines and <!-- ... --> comment blocks
    comment_pattern = re.compile(r"^(\s*\n|<!--[\s\S]*?-->\s*\n)*")
    skip = comment_pattern.match(remaining)
    if skip:
        insert_pos += skip.end()

    # Ensure a blank line separates the entry from whatever follows
    after = content[insert_pos:]
    separator = "" if after.startswith("\n") or not after.strip() else "\n"
    return content[:insert_pos] + entry + separator + content[insert_pos:]


def _append_to_project(content: str, project: str, entry: str) -> str:
    """Append entry under a ## project heading within Project Notes, creating it if needed."""
    # Look for existing ## project heading
    pattern = rf"(## {re.escape(project)}\n)"
    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        insert_pos = match.end()
        # Skip blank lines after heading
        remaining = content[insert_pos:]
        blank_match = re.match(r"^\s*\n", remaining)
        if blank_match:
            insert_pos += blank_match.end()
        return content[:insert_pos] + entry + content[insert_pos:]

    # No existing heading — find Project Notes section and append a new subsection
    notes_match = re.search(r"# Project Notes\n", content)
    if not notes_match:
        content = content.rstrip() + "\n\n# Project Notes\n\n"
        notes_match = re.search(r"# Project Notes\n", content)
        assert notes_match  # We just added it

    # Find the end of the Project Notes section (next # heading or EOF)
    section_start = notes_match.end()
    next_heading = re.search(r"\n# ", content[section_start:])
    if next_heading:
        insert_pos = section_start + next_heading.start()
    else:
        insert_pos = len(content)

    new_subsection = f"\n## {project}\n\n{entry}"
    return content[:insert_pos].rstrip() + new_subsection + "\n" + content[insert_pos:]
