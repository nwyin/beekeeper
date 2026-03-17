"""Integration tests that run the full pipeline against real repos.

All output goes to tmp dirs — never touches real vaults or filesystems.
"""

import json
from pathlib import Path

from click.testing import CliRunner

from beekeeper.cli import cli


def test_scout_then_synthesize(tmp_path: Path) -> None:
    """Full pipeline: scout a project, then synthesize into a temp vault."""
    reports_dir = tmp_path / "reports"
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "dailies").mkdir()

    runner = CliRunner()

    # Scout
    result = runner.invoke(cli, ["scout", "--project", "my-cli-tool", "--output-dir", str(reports_dir)])
    assert result.exit_code == 0, result.output
    assert "my-cli-tool" in result.output

    # Verify report was written
    report_files = list(reports_dir.rglob("my-cli-tool.json"))
    assert len(report_files) == 1
    report_data = json.loads(report_files[0].read_text())
    assert report_data["project"] == "my-cli-tool"
    assert report_data["git"]["last_commit_date"] is not None

    # Synthesize into temp vault
    date_str = report_files[0].parent.name  # e.g. "2026-03-10"
    result = runner.invoke(
        cli,
        ["synthesize", "--reports-dir", str(reports_dir), "--vault", str(vault_dir), "--date", date_str, "--target-date", date_str],
    )
    assert result.exit_code == 0, result.output
    assert "Beekeeper" in result.output or "Wrote" in result.output

    # Verify daily note was written
    note_path = vault_dir / "dailies" / f"{date_str}.md"
    assert note_path.exists()
    content = note_path.read_text()
    assert "## Beekeeper" in content
    assert "my-cli-tool" in content


def test_synthesize_idempotent(tmp_path: Path) -> None:
    """Running synthesize twice replaces the section, not duplicates it."""
    reports_dir = tmp_path / "reports"
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "dailies").mkdir()

    runner = CliRunner()

    # Scout
    runner.invoke(cli, ["scout", "--project", "my-cli-tool", "--output-dir", str(reports_dir)])
    report_files = list(reports_dir.rglob("my-cli-tool.json"))
    date_str = report_files[0].parent.name

    # Synthesize twice
    for _ in range(2):
        result = runner.invoke(
            cli,
            ["synthesize", "--reports-dir", str(reports_dir), "--vault", str(vault_dir), "--date", date_str, "--target-date", date_str],
        )
        assert result.exit_code == 0, result.output

    content = (vault_dir / "dailies" / f"{date_str}.md").read_text()
    assert content.count("## Beekeeper") == 1


def test_run_full_pipeline(tmp_path: Path) -> None:
    """Test the 'run' command scouts all registered projects and writes a daily note."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "dailies").mkdir()

    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--vault", str(vault_dir)])
    assert result.exit_code == 0, result.output
    assert "Scouting" in result.output
    assert "Wrote daily note" in result.output

    # Verify a daily note was created
    daily_files = list((vault_dir / "dailies").glob("*.md"))
    assert len(daily_files) == 1
    content = daily_files[0].read_text()
    assert "## Beekeeper" in content
