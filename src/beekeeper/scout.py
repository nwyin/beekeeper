"""Scout: collects health data for a single project."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from beekeeper.registry import ProjectConfig

logger = logging.getLogger(__name__)

SUBPROCESS_TIMEOUT = 30

# Packages that are part of venv infrastructure, not actual project deps.
# We use uv for all Python projects, so these being "outdated" is irrelevant.
IGNORED_PYTHON_DEPS = {"pip", "setuptools", "wheel"}

# Pattern matching table headers and separator lines in CLI output.
_HEADER_OR_SEPARATOR_RE = re.compile(r"^[-=|+]+$")
_HEADER_WORDS = {"Name", "Package", "Crate", "Project", "Kind", "Version", "Latest", "Compat", "Platform", "Type"}


def _is_dep_line(line: str) -> bool:
    """Return True if *line* looks like an actual dependency row, not a header or separator."""
    parts = line.split()
    if not parts:
        return False
    first = parts[0]
    if _HEADER_OR_SEPARATOR_RE.fullmatch(first):
        return False
    if first in _HEADER_WORDS:
        return False
    return True


@dataclass
class GitReport:
    last_commit_date: str | None = None
    days_since_last_commit: int | None = None
    uncommitted_changes: bool = False
    branch_count: int = 0
    current_branch: str | None = None
    error: str | None = None


@dataclass
class GitHubReport:
    open_issue_count: int = 0
    open_pr_count: int = 0
    ci_status: str | None = None  # "pass", "fail", "none"
    star_count: int = 0
    fork_count: int = 0
    error: str | None = None


@dataclass
class DependencyReport:
    outdated: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ScoutReport:
    project: str
    scouted_at: str
    git: GitReport
    github: GitHubReport
    dependencies: DependencyReport


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT, cwd=cwd)


def scout_git(project: ProjectConfig) -> GitReport:
    report = GitReport()
    cwd = project.path

    if not cwd.exists():
        report.error = f"Project path does not exist: {cwd}"
        return report

    try:
        result = _run(["git", "log", "-1", "--format=%aI"], cwd=cwd)
        if result.returncode == 0 and result.stdout.strip():
            last_commit = result.stdout.strip()
            report.last_commit_date = last_commit
            dt = datetime.fromisoformat(last_commit)
            report.days_since_last_commit = (datetime.now(timezone.utc) - dt).days
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        report.error = str(e)
        return report

    try:
        result = _run(["git", "status", "--porcelain"], cwd=cwd)
        if result.returncode == 0:
            report.uncommitted_changes = bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        result = _run(["git", "branch", "--list"], cwd=cwd)
        if result.returncode == 0:
            branches = [b.strip().lstrip("* ") for b in result.stdout.strip().splitlines() if b.strip()]
            report.branch_count = len(branches)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        result = _run(["git", "branch", "--show-current"], cwd=cwd)
        if result.returncode == 0:
            report.current_branch = result.stdout.strip() or None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return report


def _detect_github_remote(path: Path) -> str | None:
    """Try to extract an owner/repo slug from the git remote origin URL."""
    try:
        result = _run(["git", "remote", "get-url", "origin"], cwd=path)
        if result.returncode == 0:
            url = result.stdout.strip()
            match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
            if match:
                return match.group(1)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def scout_github(project: ProjectConfig) -> GitHubReport:
    report = GitHubReport()

    github: str | None = project.github or _detect_github_remote(project.path)
    if not github:
        report.error = "No GitHub remote configured"
        return report
    assert isinstance(github, str)

    try:
        result = _run(["gh", "repo", "view", github, "--json", "stargazerCount,forkCount"])
        if result.returncode == 0:
            data = json.loads(result.stdout)
            report.star_count = data.get("stargazerCount", 0)
            report.fork_count = data.get("forkCount", 0)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
        report.error = str(e)
        return report

    try:
        result = _run(["gh", "issue", "list", "--repo", github, "--state", "open", "--json", "number"])
        if result.returncode == 0:
            report.open_issue_count = len(json.loads(result.stdout))
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    try:
        result = _run(["gh", "pr", "list", "--repo", github, "--state", "open", "--json", "number"])
        if result.returncode == 0:
            report.open_pr_count = len(json.loads(result.stdout))
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    try:
        result = _run(["gh", "run", "list", "--repo", github, "--limit", "1", "--json", "conclusion"])
        if result.returncode == 0:
            runs = json.loads(result.stdout)
            if runs:
                conclusion = runs[0].get("conclusion", "")
                if conclusion == "success":
                    report.ci_status = "pass"
                elif conclusion in ("failure", "timed_out", "cancelled"):
                    report.ci_status = "fail"
                else:
                    report.ci_status = "none"
            else:
                report.ci_status = "none"
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    return report


def scout_dependencies(project: ProjectConfig) -> DependencyReport:
    report = DependencyReport()

    try:
        if project.stack == "rust":
            result = _run(["cargo", "outdated", "--root-deps-only", "--exit-code", "0"], cwd=project.path)
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    if _is_dep_line(line):
                        report.outdated.append(line.split()[0])
            elif result.returncode != 0:
                report.error = f"cargo outdated failed: {result.stderr.strip()}"

        elif project.stack == "python":
            result = _run(["uv", "pip", "list", "--outdated"], cwd=project.path)
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    if _is_dep_line(line):
                        pkg = line.split()[0]
                        if pkg not in IGNORED_PYTHON_DEPS:
                            report.outdated.append(pkg)
            elif result.returncode != 0:
                report.error = f"uv pip list --outdated failed: {result.stderr.strip()}"

        elif project.stack == "typescript":
            result = _run(["bun", "outdated"], cwd=project.path)
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    # bun outdated uses pipe-delimited tables: "| package (dev) | 1.0 | 1.1 | 1.1 |"
                    line = line.strip()
                    if line.startswith("|") and not line.startswith("|--") and "Package" not in line:
                        cells = [c.strip() for c in line.split("|") if c.strip()]
                        if cells:
                            # Strip trailing "(dev)" marker
                            pkg = cells[0].removesuffix("(dev)").strip()
                            if pkg:
                                report.outdated.append(pkg)
            elif result.returncode != 0:
                report.error = f"bun outdated failed: {result.stderr.strip()}"

        else:
            report.error = f"Dependency checking not supported for stack: {project.stack}"

    except subprocess.TimeoutExpired:
        report.error = "Dependency check timed out"
    except FileNotFoundError as e:
        report.error = f"Tool not found: {e}"

    return report


def scout_project(project: ProjectConfig) -> ScoutReport:
    logger.info("Scouting %s", project.name)
    with ThreadPoolExecutor(max_workers=3) as pool:
        git_future = pool.submit(scout_git, project)
        github_future = pool.submit(scout_github, project)
        deps_future = pool.submit(scout_dependencies, project)
        return ScoutReport(
            project=project.name,
            scouted_at=datetime.now(timezone.utc).isoformat(),
            git=git_future.result(),
            github=github_future.result(),
            dependencies=deps_future.result(),
        )


def save_report(report: ScoutReport, base_dir: Path | None = None) -> Path:
    if base_dir is None:
        base_dir = Path(__file__).resolve().parents[2] / "reports"

    today = datetime.now().strftime("%Y-%m-%d")
    report_dir = base_dir / today
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / f"{report.project}.json"
    with open(report_path, "w") as f:
        json.dump(asdict(report), f, indent=2)

    return report_path
