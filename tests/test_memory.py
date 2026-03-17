"""Tests for the memory module."""

from pathlib import Path

from beekeeper.memory import append_memo, load_memory


def test_load_memory_returns_content(tmp_path: Path) -> None:
    mem = tmp_path / "memory.md"
    mem.write_text("# Goals\n\n1. Ship stuff\n")
    assert "Ship stuff" in load_memory(mem)


def test_load_memory_missing_file(tmp_path: Path) -> None:
    assert load_memory(tmp_path / "nope.md") == ""


def test_append_memo_general(tmp_path: Path) -> None:
    mem = tmp_path / "memory.md"
    mem.write_text("# Strategic Goals\n\n# Current Focus\n\n# Project Notes\n\n# Decisions\n\n")

    append_memo("focusing on my-webapp", memory_path=mem)

    content = mem.read_text()
    assert "focusing on my-webapp" in content
    # Should be under Current Focus
    lines = content.split("\n")
    focus_idx = next(i for i, line in enumerate(lines) if "Current Focus" in line)
    memo_idx = next(i for i, line in enumerate(lines) if "focusing on my-webapp" in line)
    assert memo_idx > focus_idx


def test_append_memo_with_comments(tmp_path: Path) -> None:
    mem = tmp_path / "memory.md"
    mem.write_text("# Current Focus\n\n<!-- What are you working on? -->\n\n# Decisions\n\n")

    append_memo("research this week", memory_path=mem)

    content = mem.read_text()
    assert "research this week" in content
    # Should appear after the comment
    assert content.index("<!-- What are you working on? -->") < content.index("research this week")


def test_append_memo_project_new(tmp_path: Path) -> None:
    mem = tmp_path / "memory.md"
    mem.write_text("# Project Notes\n\n# Decisions\n\n")

    append_memo("shelved for now", project="my-cli-tool", memory_path=mem)

    content = mem.read_text()
    assert "## my-cli-tool" in content
    assert "shelved for now" in content


def test_append_memo_project_existing(tmp_path: Path) -> None:
    mem = tmp_path / "memory.md"
    mem.write_text("# Project Notes\n\n## my-cli-tool\n\n- old note\n\n# Decisions\n\n")

    append_memo("new context", project="my-cli-tool", memory_path=mem)

    content = mem.read_text()
    assert "old note" in content
    assert "new context" in content
    # Both should be under my-cli-tool
    assert content.index("## my-cli-tool") < content.index("new context")


def test_append_memo_creates_scaffold(tmp_path: Path) -> None:
    mem = tmp_path / "memory.md"
    # File doesn't exist yet
    append_memo("first note", memory_path=mem)

    content = mem.read_text()
    assert "# Current Focus" in content
    assert "first note" in content


def test_append_memo_multiple_projects(tmp_path: Path) -> None:
    mem = tmp_path / "memory.md"
    mem.write_text("# Project Notes\n\n# Decisions\n\n")

    append_memo("note A", project="alpha", memory_path=mem)
    append_memo("note B", project="beta", memory_path=mem)

    content = mem.read_text()
    assert "## alpha" in content
    assert "## beta" in content
    assert "note A" in content
    assert "note B" in content


def test_memo_has_timestamp(tmp_path: Path) -> None:
    mem = tmp_path / "memory.md"
    mem.write_text("# Current Focus\n\n")

    append_memo("test", memory_path=mem)

    content = mem.read_text()
    # Should contain a date like [2026-03-10]
    import re

    assert re.search(r"\[\d{4}-\d{2}-\d{2}\]", content)
