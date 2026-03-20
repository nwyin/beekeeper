"""Tests for scout module."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from beekeeper.registry import ProjectConfig
from beekeeper.scout import (
    DependencyReport,
    GitHubReport,
    GitReport,
    ScoutReport,
    save_report,
    scout_dependencies,
    scout_git,
    scout_github,
)


def _make_project(tmp_path: Path, **kwargs) -> ProjectConfig:
    defaults = {
        "name": "testproject",
        "path": tmp_path,
        "github": "user/testproject",
        "type": "tool",
        "attention": "focus",
        "stack": "rust",
    }
    defaults.update(kwargs)
    return ProjectConfig(**defaults)


class TestScoutGit:
    def test_nonexistent_path(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, path=tmp_path / "nonexistent")
        report = scout_git(project)
        assert report.error is not None
        assert "does not exist" in report.error

    def test_git_log_success(self, tmp_path: Path) -> None:
        mock_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="2026-03-09T10:00:00-05:00\n", stderr="")
        with patch("beekeeper.scout._run", return_value=mock_result):
            project = _make_project(tmp_path)
            report = scout_git(project)
            assert report.last_commit_date == "2026-03-09T10:00:00-05:00"
            assert report.days_since_last_commit is not None

    def test_git_timeout(self, tmp_path: Path) -> None:
        with patch("beekeeper.scout._run", side_effect=subprocess.TimeoutExpired("git", 30)):
            project = _make_project(tmp_path)
            report = scout_git(project)
            assert report.error is not None

    def test_git_not_found(self, tmp_path: Path) -> None:
        with patch("beekeeper.scout._run", side_effect=FileNotFoundError("git")):
            project = _make_project(tmp_path)
            report = scout_git(project)
            assert report.error is not None


class TestScoutGitHub:
    def test_no_github_remote(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, github=None)
        report = scout_github(project)
        assert report.error == "No GitHub remote configured"

    def test_repo_view_success(self, tmp_path: Path) -> None:
        responses = {
            0: subprocess.CompletedProcess(args=[], returncode=0, stdout='{"stargazerCount": 5, "forkCount": 2}', stderr=""),
            1: subprocess.CompletedProcess(args=[], returncode=0, stdout='[{"number": 1}, {"number": 2}]', stderr=""),
            2: subprocess.CompletedProcess(args=[], returncode=0, stdout='[{"number": 3}]', stderr=""),
            3: subprocess.CompletedProcess(args=[], returncode=0, stdout='[{"conclusion": "success"}]', stderr=""),
        }
        call_count = {"n": 0}

        def mock_run(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx]

        with patch("beekeeper.scout._run", side_effect=mock_run):
            project = _make_project(tmp_path)
            report = scout_github(project)
            assert report.star_count == 5
            assert report.fork_count == 2
            assert report.open_issue_count == 2
            assert report.open_pr_count == 1
            assert report.ci_status == "pass"

    def test_detect_github_from_git_remote(self, tmp_path: Path) -> None:
        """When github is None in registry, fall back to parsing git remote."""
        git_remote_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="git@github.com:nwyin/irradiate.git\n", stderr=""
        )
        gh_results = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout='{"stargazerCount": 3, "forkCount": 0}', stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr=""),
        ]
        call_count = {"n": 0}

        def mock_run(args, **kwargs):
            if "get-url" in args:
                return git_remote_result
            idx = call_count["n"]
            call_count["n"] += 1
            return gh_results[idx]

        with patch("beekeeper.scout._run", side_effect=mock_run):
            project = _make_project(tmp_path, github=None)
            report = scout_github(project)
            assert report.error is None
            assert report.star_count == 3

    def test_detect_github_from_https_remote(self, tmp_path: Path) -> None:
        """HTTPS remotes should also be detected."""
        git_remote_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="https://github.com/nwyin/irradiate.git\n", stderr=""
        )
        gh_results = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout='{"stargazerCount": 0, "forkCount": 0}', stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr=""),
        ]
        call_count = {"n": 0}

        def mock_run(args, **kwargs):
            if "get-url" in args:
                return git_remote_result
            idx = call_count["n"]
            call_count["n"] += 1
            return gh_results[idx]

        with patch("beekeeper.scout._run", side_effect=mock_run):
            project = _make_project(tmp_path, github=None)
            report = scout_github(project)
            assert report.error is None

    def test_gh_timeout(self, tmp_path: Path) -> None:
        with patch("beekeeper.scout._run", side_effect=subprocess.TimeoutExpired("gh", 30)):
            project = _make_project(tmp_path)
            report = scout_github(project)
            assert report.error is not None


class TestScoutDependencies:
    def test_unsupported_stack(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, stack="markdown")
        report = scout_dependencies(project)
        assert report.error is not None
        assert "not supported" in report.error

    def test_cargo_outdated_success(self, tmp_path: Path) -> None:
        cargo_output = "Name    Project  Compat  Latest  Kind\n----    -------  ------  ------  ----\nreqwest 0.11.0   0.12.0  0.12.0  Normal\nserde   1.0.0    1.1.0   1.1.0   Normal\n"
        mock_result = subprocess.CompletedProcess(args=[], returncode=0, stdout=cargo_output, stderr="")
        with patch("beekeeper.scout._run", return_value=mock_result):
            project = _make_project(tmp_path, stack="rust")
            report = scout_dependencies(project)
            assert "reqwest" in report.outdated
            assert "serde" in report.outdated

    def test_tool_not_found(self, tmp_path: Path) -> None:
        with patch("beekeeper.scout._run", side_effect=FileNotFoundError("cargo")):
            project = _make_project(tmp_path, stack="rust")
            report = scout_dependencies(project)
            assert report.error is not None
            assert "not found" in report.error.lower()

    def test_bun_outdated_success(self, tmp_path: Path) -> None:
        bun_output = (
            "bun outdated v1.3.9 (cf6cdbbb)\n"
            "|--------------------------------------------------------|\n"
            "| Package                    | Current | Update | Latest |\n"
            "|----------------------------|---------|--------|--------|\n"
            "| @biomejs/biome (dev)       | 1.9.4   | 1.9.4  | 2.4.6  |\n"
            "|----------------------------|---------|--------|--------|\n"
            "| turbo (dev)                | 2.8.10  | 2.8.15 | 2.8.15 |\n"
            "|--------------------------------------------------------|\n"
        )
        mock_result = subprocess.CompletedProcess(args=[], returncode=0, stdout=bun_output, stderr="")
        with patch("beekeeper.scout._run", return_value=mock_result):
            project = _make_project(tmp_path, stack="typescript")
            report = scout_dependencies(project)
            assert "@biomejs/biome" in report.outdated
            assert "turbo" in report.outdated
            assert len(report.outdated) == 2
            # Should not contain table borders
            assert not any("|" in dep for dep in report.outdated)

    def test_timeout(self, tmp_path: Path) -> None:
        with patch("beekeeper.scout._run", side_effect=subprocess.TimeoutExpired("cargo", 30)):
            project = _make_project(tmp_path, stack="rust")
            report = scout_dependencies(project)
            assert report.error == "Dependency check timed out"


class TestSaveReport:
    def test_save_creates_file(self, tmp_path: Path) -> None:
        report = ScoutReport(
            project="testproject",
            scouted_at="2026-03-10T00:00:00+00:00",
            git=GitReport(),
            github=GitHubReport(),
            dependencies=DependencyReport(),
        )
        path = save_report(report, base_dir=tmp_path)
        assert path.exists()
        assert path.name == "testproject.json"

        data = json.loads(path.read_text())
        assert data["project"] == "testproject"
        assert data["scouted_at"] == "2026-03-10T00:00:00+00:00"
        assert "git" in data
        assert "github" in data
        assert "dependencies" in data

    def test_save_creates_date_directory(self, tmp_path: Path) -> None:
        report = ScoutReport(
            project="test",
            scouted_at="2026-03-10T00:00:00+00:00",
            git=GitReport(),
            github=GitHubReport(),
            dependencies=DependencyReport(),
        )
        path = save_report(report, base_dir=tmp_path)
        # Should be in a date-stamped subdirectory
        assert path.parent.name  # date directory exists
        assert path.parent.parent == tmp_path
