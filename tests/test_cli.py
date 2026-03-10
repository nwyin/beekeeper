"""Tests for CLI entry point."""

from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

from click.testing import CliRunner

from mission_control.cli import cli


def test_scout_unknown_project(tmp_path: Path) -> None:
    toml_file = tmp_path / "projects.toml"
    toml_file.write_text(
        dedent("""\
        [projects.alpha]
        path = "/tmp/alpha"
    """)
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["scout", "--project", "nonexistent", "--registry", str(toml_file)])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_scout_single_project(tmp_path: Path) -> None:
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()

    toml_file = tmp_path / "projects.toml"
    toml_file.write_text(
        dedent(f"""\
        [projects.myproject]
        path = "{project_dir}"
        stack = "markdown"
    """)
    )

    output_dir = tmp_path / "reports"

    with patch("mission_control.cli.scout_project") as mock_scout:
        from mission_control.scout import DependencyReport, GitHubReport, GitReport, ScoutReport

        mock_scout.return_value = ScoutReport(
            project="myproject",
            scouted_at="2026-03-10T00:00:00+00:00",
            git=GitReport(),
            github=GitHubReport(),
            dependencies=DependencyReport(),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["scout", "--project", "myproject", "--registry", str(toml_file), "--output-dir", str(output_dir)])
        assert result.exit_code == 0
        assert "myproject" in result.output


def test_scout_resilient_to_failure(tmp_path: Path) -> None:
    toml_file = tmp_path / "projects.toml"
    toml_file.write_text(
        dedent("""\
        [projects.broken]
        path = "/tmp/broken"
        stack = "markdown"

        [projects.working]
        path = "/tmp/working"
        stack = "markdown"
    """)
    )

    output_dir = tmp_path / "reports"
    call_count = {"n": 0}

    def mock_scout(config):
        call_count["n"] += 1
        if config.name == "broken":
            raise RuntimeError("Scout failed!")
        from mission_control.scout import DependencyReport, GitHubReport, GitReport, ScoutReport

        return ScoutReport(
            project=config.name,
            scouted_at="2026-03-10T00:00:00+00:00",
            git=GitReport(),
            github=GitHubReport(),
            dependencies=DependencyReport(),
        )

    with patch("mission_control.cli.scout_project", side_effect=mock_scout):
        runner = CliRunner()
        result = runner.invoke(cli, ["scout", "--registry", str(toml_file), "--output-dir", str(output_dir)])
        # Should not crash despite broken project
        assert result.exit_code == 0
        assert "FAILED" in result.output
        assert call_count["n"] == 2  # Both projects were attempted
