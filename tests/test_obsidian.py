"""Tests for Obsidian writer."""

from pathlib import Path

from beekeeper.obsidian import SECTION_HEADER, write_daily_note


class TestWriteDailyNote:
    def test_creates_new_file_with_template(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "dailies").mkdir()

        path = write_daily_note("## Beekeeper\n\nTest content.\n", vault_path=vault, date="2026-03-11")
        assert path.exists()
        content = path.read_text()
        assert "date: 2026-03-11" in content
        assert "tags: [daily]" in content
        assert "## Beekeeper" in content
        assert "Test content." in content

    def test_appends_to_existing_file(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        dailies = vault / "dailies"
        dailies.mkdir(parents=True)

        existing = dailies / "2026-03-11.md"
        existing.write_text("- had a productive day\n- shipped some code\n")

        path = write_daily_note("## Beekeeper\n\nNew section.\n", vault_path=vault, date="2026-03-11")
        content = path.read_text()
        assert "had a productive day" in content
        assert "## Beekeeper" in content
        assert "New section." in content

    def test_idempotent_replaces_existing_section(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        dailies = vault / "dailies"
        dailies.mkdir(parents=True)

        existing = dailies / "2026-03-11.md"
        existing.write_text("- my notes\n\n## Beekeeper\n\nOld content.\n")

        path = write_daily_note("## Beekeeper\n\nUpdated content.\n", vault_path=vault, date="2026-03-11")
        content = path.read_text()
        assert "my notes" in content
        assert "Updated content." in content
        assert "Old content." not in content
        # Should only have one Beekeeper section
        assert content.count(SECTION_HEADER) == 1

    def test_preserves_other_sections(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        dailies = vault / "dailies"
        dailies.mkdir(parents=True)

        existing = dailies / "2026-03-11.md"
        existing.write_text("## Morning\n\nGood morning.\n\n## Beekeeper\n\nOld.\n\n## Evening\n\nGood evening.\n")

        path = write_daily_note("## Beekeeper\n\nRefreshed.\n", vault_path=vault, date="2026-03-11")
        content = path.read_text()
        assert "Good morning." in content
        assert "Good evening." in content
        assert "Refreshed." in content
        assert "Old." not in content

    def test_creates_dailies_directory(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        # Don't create dailies/ — it should be created automatically
        vault.mkdir()

        path = write_daily_note("## Beekeeper\n\nContent.\n", vault_path=vault, date="2026-03-11")
        assert path.exists()
        assert path.parent.name == "dailies"
