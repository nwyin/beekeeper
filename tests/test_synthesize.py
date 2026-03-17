"""Tests for synthesizer module."""

import json
from pathlib import Path

from beekeeper.synthesize import ActionItem, SynthesisResult, load_reports, render_markdown, synthesize


def _make_report(
    name: str = "testproject",
    days_since: int = 3,
    uncommitted: bool = False,
    ci_status: str = "pass",
    open_issues: int = 0,
    open_prs: int = 0,
    stars: int = 10,
    forks: int = 1,
    outdated: list[str] | None = None,
) -> dict:
    return {
        "project": name,
        "scouted_at": "2026-03-10T00:00:00+00:00",
        "git": {
            "last_commit_date": "2026-03-07T10:00:00+00:00",
            "days_since_last_commit": days_since,
            "uncommitted_changes": uncommitted,
            "branch_count": 2,
            "current_branch": "main",
            "error": None,
        },
        "github": {
            "open_issue_count": open_issues,
            "open_pr_count": open_prs,
            "ci_status": ci_status,
            "star_count": stars,
            "fork_count": forks,
            "error": None,
        },
        "dependencies": {
            "outdated": outdated or [],
            "error": None,
        },
    }


class TestLoadReports:
    def test_load_reports_from_dir(self, tmp_path: Path) -> None:
        day_dir = tmp_path / "2026-03-10"
        day_dir.mkdir()
        report = _make_report("alpha")
        (day_dir / "alpha.json").write_text(json.dumps(report))

        reports = load_reports(tmp_path, "2026-03-10")
        assert len(reports) == 1
        assert reports[0]["project"] == "alpha"

    def test_load_reports_missing_date(self, tmp_path: Path) -> None:
        reports = load_reports(tmp_path, "2099-01-01")
        assert reports == []

    def test_load_reports_invalid_json(self, tmp_path: Path) -> None:
        day_dir = tmp_path / "2026-03-10"
        day_dir.mkdir()
        (day_dir / "broken.json").write_text("not json{{{")

        reports = load_reports(tmp_path, "2026-03-10")
        assert reports == []

    def test_load_reports_multiple(self, tmp_path: Path) -> None:
        day_dir = tmp_path / "2026-03-10"
        day_dir.mkdir()
        (day_dir / "alpha.json").write_text(json.dumps(_make_report("alpha")))
        (day_dir / "beta.json").write_text(json.dumps(_make_report("beta")))

        reports = load_reports(tmp_path, "2026-03-10")
        assert len(reports) == 2


class TestSynthesize:
    def test_healthy_project(self, tmp_path: Path) -> None:
        day_dir = tmp_path / "2026-03-10"
        day_dir.mkdir()
        (day_dir / "healthy.json").write_text(json.dumps(_make_report("healthy", days_since=1)))

        result = synthesize(tmp_path, date="2026-03-10")
        assert len(result.project_summaries) == 1
        assert "healthy" in result.project_summaries[0].lower()
        # No critical actions for a healthy project
        critical = [a for a in result.action_items if a.category in ("ci_failure", "stale")]
        assert len(critical) == 0

    def test_stale_project_creates_action(self, tmp_path: Path) -> None:
        day_dir = tmp_path / "2026-03-10"
        day_dir.mkdir()
        (day_dir / "stale.json").write_text(json.dumps(_make_report("stale", days_since=20)))

        result = synthesize(tmp_path, date="2026-03-10")
        stale_actions = [a for a in result.action_items if a.category == "stale"]
        assert len(stale_actions) == 1
        assert stale_actions[0].project == "stale"

    def test_ci_failure_creates_action(self, tmp_path: Path) -> None:
        day_dir = tmp_path / "2026-03-10"
        day_dir.mkdir()
        (day_dir / "broken.json").write_text(json.dumps(_make_report("broken", ci_status="fail")))

        result = synthesize(tmp_path, date="2026-03-10")
        ci_actions = [a for a in result.action_items if a.category == "ci_failure"]
        assert len(ci_actions) == 1

    def test_outdated_deps_creates_action(self, tmp_path: Path) -> None:
        day_dir = tmp_path / "2026-03-10"
        day_dir.mkdir()
        (day_dir / "old.json").write_text(json.dumps(_make_report("old", outdated=["reqwest", "serde"])))

        result = synthesize(tmp_path, date="2026-03-10")
        dep_actions = [a for a in result.action_items if a.category == "outdated_deps"]
        assert len(dep_actions) == 1
        assert "reqwest" in dep_actions[0].description

    def test_open_issues_creates_action(self, tmp_path: Path) -> None:
        day_dir = tmp_path / "2026-03-10"
        day_dir.mkdir()
        (day_dir / "issues.json").write_text(json.dumps(_make_report("issues", open_issues=3)))

        result = synthesize(tmp_path, date="2026-03-10")
        issue_actions = [a for a in result.action_items if a.category == "open_issues"]
        assert len(issue_actions) == 1

    def test_uncommitted_changes_creates_action(self, tmp_path: Path) -> None:
        day_dir = tmp_path / "2026-03-10"
        day_dir.mkdir()
        (day_dir / "dirty.json").write_text(json.dumps(_make_report("dirty", uncommitted=True)))

        result = synthesize(tmp_path, date="2026-03-10")
        uncommitted = [a for a in result.action_items if a.category == "uncommitted"]
        assert len(uncommitted) == 1

    def test_no_reports_returns_empty(self, tmp_path: Path) -> None:
        result = synthesize(tmp_path, date="2099-01-01")
        assert result.project_summaries == []
        assert result.action_items == []

    def test_overview_reflects_critical_items(self, tmp_path: Path) -> None:
        day_dir = tmp_path / "2026-03-10"
        day_dir.mkdir()
        (day_dir / "broken.json").write_text(json.dumps(_make_report("broken", ci_status="fail")))
        (day_dir / "healthy.json").write_text(json.dumps(_make_report("healthy")))

        result = synthesize(tmp_path, date="2026-03-10")
        assert "2 projects" in result.overview
        assert "critical" in result.overview.lower()


class TestRenderMarkdown:
    def test_basic_render(self) -> None:
        result = SynthesisResult(
            date="2026-03-10",
            project_summaries=["**alpha**: Last commit 3 days ago. CI passing."],
            action_items=[],
            overview="Scanned 1 project. Everything looks healthy.",
        )
        md = render_markdown(result)
        assert md.startswith("## Beekeeper")
        assert "Everything looks healthy" in md
        assert "**alpha**" in md

    def test_render_with_actions(self) -> None:
        result = SynthesisResult(
            date="2026-03-10",
            project_summaries=["**beta**: CI failing."],
            action_items=[ActionItem(project="beta", category="ci_failure", description="CI is failing")],
            overview="Scanned 1 project. 1 critical item needs attention.",
        )
        md = render_markdown(result)
        assert "### Action items" in md
        assert "ci_failure" in md
        assert "### Project status" in md

    def test_render_no_projects(self) -> None:
        result = SynthesisResult(
            date="2026-03-10",
            project_summaries=[],
            action_items=[],
            overview="Scanned 0 projects. Everything looks healthy.",
        )
        md = render_markdown(result)
        assert "## Beekeeper" in md
