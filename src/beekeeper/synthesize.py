"""Synthesizer: reads scout reports and generates narrative summaries."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

STALENESS_THRESHOLD_DAYS = 14


@dataclass
class ActionItem:
    project: str
    category: str  # "stale", "ci_failure", "open_issues", "open_prs", "outdated_deps", "uncommitted"
    description: str


@dataclass
class SynthesisResult:
    date: str
    project_summaries: list[str]
    action_items: list[ActionItem]
    overview: str
    llm_analysis: str | None = None


def load_reports(reports_dir: Path, date: str | None = None) -> list[dict]:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    day_dir = reports_dir / date
    if not day_dir.exists():
        logger.warning("No reports found for %s at %s", date, day_dir)
        return []

    reports = []
    for report_file in sorted(day_dir.glob("*.json")):
        try:
            with open(report_file) as f:
                reports.append(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read %s: %s", report_file, e)

    return reports


def _summarize_project(report: dict) -> str:
    name = report["project"]
    git = report.get("git", {})
    github = report.get("github", {})
    deps = report.get("dependencies", {})

    parts = [f"**{name}**:"]

    # Git status
    days = git.get("days_since_last_commit")
    if days is not None:
        if days == 0:
            parts.append("Active today.")
        elif days == 1:
            parts.append("Last commit yesterday.")
        elif days < STALENESS_THRESHOLD_DAYS:
            parts.append(f"Last commit {days} days ago.")
        else:
            parts.append(f"Last commit {days} days ago (stale).")

    if git.get("uncommitted_changes"):
        parts.append("Has uncommitted changes.")

    # GitHub
    stars = github.get("star_count", 0)
    forks = github.get("fork_count", 0)
    issues = github.get("open_issue_count", 0)
    prs = github.get("open_pr_count", 0)
    ci = github.get("ci_status")

    github_bits = []
    if stars:
        github_bits.append(f"{stars} star{'s' if stars != 1 else ''}")
    if forks:
        github_bits.append(f"{forks} fork{'s' if forks != 1 else ''}")
    if github_bits:
        parts.append(f"{', '.join(github_bits)}.")

    if issues:
        parts.append(f"{issues} open issue{'s' if issues != 1 else ''}.")
    if prs:
        parts.append(f"{prs} open PR{'s' if prs != 1 else ''}.")
    if ci == "fail":
        parts.append("CI is failing.")
    elif ci == "pass":
        parts.append("CI passing.")

    # Dependencies
    outdated = deps.get("outdated", [])
    if outdated:
        parts.append(f"{len(outdated)} outdated dep{'s' if len(outdated) != 1 else ''}: {', '.join(outdated[:5])}.")

    return " ".join(parts)


def _extract_actions(report: dict) -> list[ActionItem]:
    name = report["project"]
    git = report.get("git", {})
    github = report.get("github", {})
    deps = report.get("dependencies", {})
    actions = []

    days = git.get("days_since_last_commit")
    if days is not None and days >= STALENESS_THRESHOLD_DAYS:
        actions.append(
            ActionItem(
                project=name,
                category="stale",
                description=f"No commits in {days} days",
            )
        )

    if git.get("uncommitted_changes"):
        actions.append(
            ActionItem(
                project=name,
                category="uncommitted",
                description="Uncommitted changes in working tree",
            )
        )

    ci = github.get("ci_status")
    if ci == "fail":
        actions.append(
            ActionItem(
                project=name,
                category="ci_failure",
                description="CI is failing",
            )
        )

    issues = github.get("open_issue_count", 0)
    if issues > 0:
        actions.append(
            ActionItem(
                project=name,
                category="open_issues",
                description=f"{issues} open issue{'s' if issues != 1 else ''}",
            )
        )

    prs = github.get("open_pr_count", 0)
    if prs > 0:
        actions.append(
            ActionItem(
                project=name,
                category="open_prs",
                description=f"{prs} open PR{'s' if prs != 1 else ''}",
            )
        )

    outdated = deps.get("outdated", [])
    if outdated:
        actions.append(
            ActionItem(
                project=name,
                category="outdated_deps",
                description=f"Outdated: {', '.join(outdated[:10])}",
            )
        )

    return actions


def _generate_overview(project_summaries: list[str], action_items: list[ActionItem]) -> str:
    n_projects = len(project_summaries)
    n_actions = len(action_items)

    critical = [a for a in action_items if a.category in ("ci_failure", "stale")]
    parts = [f"Scanned {n_projects} project{'s' if n_projects != 1 else ''}."]

    if not action_items:
        parts.append("Everything looks healthy.")
    elif critical:
        parts.append(f"{len(critical)} critical item{'s' if len(critical) != 1 else ''} need{'s' if len(critical) == 1 else ''} attention.")
    else:
        parts.append(f"{n_actions} item{'s' if n_actions != 1 else ''} to review.")

    return " ".join(parts)


def synthesize(reports_dir: Path, date: str | None = None) -> SynthesisResult:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    reports = load_reports(reports_dir, date)

    project_summaries = []
    all_actions: list[ActionItem] = []

    for report in reports:
        project_summaries.append(_summarize_project(report))
        all_actions.extend(_extract_actions(report))

    overview = _generate_overview(project_summaries, all_actions)

    return SynthesisResult(
        date=date,
        project_summaries=project_summaries,
        action_items=all_actions,
        overview=overview,
    )


def render_markdown(result: SynthesisResult) -> str:
    lines = ["## Beekeeper", "", result.overview, ""]

    if result.llm_analysis:
        lines.append("### Analysis")
        lines.append("")
        lines.append(result.llm_analysis)
        lines.append("")

    if result.action_items:
        lines.append("### Action items")
        lines.append("")
        for item in result.action_items:
            lines.append(f"- **{item.project}** ({item.category}): {item.description}")
        lines.append("")

    lines.append("### Project status")
    lines.append("")
    for summary in result.project_summaries:
        lines.append(f"- {summary}")
    lines.append("")

    return "\n".join(lines)
