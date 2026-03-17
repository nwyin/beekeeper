"""CLI entry point for beekeeper."""

from __future__ import annotations

import json
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import click

from beekeeper.llm import generate_analysis, load_registry_text
from beekeeper.memory import append_memo, load_memory
from beekeeper.obsidian import write_daily_note
from beekeeper.paths import DEFAULT_REPORTS_DIR, STATE_DIR
from beekeeper.registry import load_registry
from beekeeper.scout import save_report, scout_project
from beekeeper.synthesize import load_reports, render_markdown, synthesize

logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@cli.command()
@click.option("--project", "-p", "project_name", default=None, help="Scout a specific project (default: all)")
@click.option("--registry", "-r", "registry_path", default=None, type=click.Path(exists=True, path_type=Path))
@click.option("--output-dir", "-o", "output_dir", default=None, type=click.Path(path_type=Path))
def scout(project_name: str | None, registry_path: Path | None, output_dir: Path | None) -> None:
    """Scout project health and write JSON reports."""
    projects = load_registry(registry_path)

    if project_name:
        if project_name not in projects:
            raise click.ClickException(f"Project '{project_name}' not found in registry. Available: {', '.join(projects.keys())}")
        targets = {project_name: projects[project_name]}
    else:
        targets = projects

    if output_dir is None:
        output_dir = DEFAULT_REPORTS_DIR

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(scout_project, config): name for name, config in targets.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                report = future.result()
                path = save_report(report, base_dir=output_dir)
                click.echo(f"[{name}] Report saved to {path}")
            except Exception:
                logger.exception("Failed to scout %s", name)
                click.echo(f"[{name}] FAILED (see logs)")


@cli.command()
@click.option("--reports-dir", "-r", default=None, type=click.Path(exists=True, path_type=Path), help="Reports directory")
@click.option("--vault", "-V", default=None, type=click.Path(path_type=Path), help="Obsidian vault path")
@click.option("--date", "-d", default=None, help="Date to synthesize (YYYY-MM-DD, default: today)")
@click.option("--target-date", "-t", default=None, help="Target daily note date (YYYY-MM-DD, default: today)")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis")
def synthesize_cmd(reports_dir: Path | None, vault: Path | None, date: str | None, target_date: str | None, no_llm: bool) -> None:
    """Synthesize scout reports into an Obsidian daily note."""
    if reports_dir is None:
        reports_dir = DEFAULT_REPORTS_DIR

    result = synthesize(reports_dir, date=date)

    if not result.project_summaries:
        click.echo("No reports found to synthesize.")
        return

    if not no_llm:
        click.echo("Generating PM analysis...")
        reports = load_reports(reports_dir, date=date)
        result.llm_analysis = generate_analysis(reports, load_registry_text(), load_memory())

    markdown = render_markdown(result)
    note_path = write_daily_note(markdown, vault_path=vault, date=target_date)
    click.echo(f"Wrote Beekeeper section to {note_path}")
    click.echo(f"  {len(result.project_summaries)} projects, {len(result.action_items)} action items")


@cli.command()
@click.option("--registry", "-r", "registry_path", default=None, type=click.Path(exists=True, path_type=Path))
@click.option("--vault", "-V", default=None, type=click.Path(path_type=Path), help="Obsidian vault path")
@click.option("--target-date", "-t", default=None, help="Target daily note date (YYYY-MM-DD, default: today)")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis")
def run(registry_path: Path | None, vault: Path | None, target_date: str | None, no_llm: bool) -> None:
    """Run the full pipeline: scout all projects, then synthesize."""
    reports_dir = DEFAULT_REPORTS_DIR
    log_dir = STATE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")

    # Set up file logging
    file_handler = logging.FileHandler(log_dir / f"{today}.log")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(file_handler)

    # Scout all projects
    projects = load_registry(registry_path)
    click.echo(f"Scouting {len(projects)} projects...")

    succeeded = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(scout_project, config): name for name, config in projects.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                report = future.result()
                save_report(report, base_dir=reports_dir)
                succeeded += 1
            except Exception:
                logger.exception("Failed to scout %s", name)
                failed += 1

    click.echo(f"  Scouted: {succeeded} OK, {failed} failed")

    # Synthesize
    result = synthesize(reports_dir, date=today)
    if result.project_summaries:
        if not no_llm:
            click.echo("  Generating PM analysis...")
            reports = load_reports(reports_dir, date=today)
            result.llm_analysis = generate_analysis(reports, load_registry_text(), load_memory())

        markdown = render_markdown(result)
        note_path = write_daily_note(markdown, vault_path=vault, date=target_date)
        click.echo(f"  Wrote daily note: {note_path}")
        click.echo(f"  {len(result.action_items)} action items")
    else:
        click.echo("  No reports to synthesize.")


@cli.command()
@click.argument("text")
@click.option("--project", "-p", default=None, help="Attach memo to a specific project")
def memo(text: str, project: str | None) -> None:
    """Add a timestamped memo to PM memory.

    Examples:
        beekeeper memo "focusing on my-webapp this week"
        beekeeper memo -p my-cli-tool "shelved until v2 ships"
    """
    path = append_memo(text, project=project)
    if project:
        click.echo(f"Added memo for {project} to {path}")
    else:
        click.echo(f"Added memo to {path}")


@cli.command()
@click.option("--date", "-d", default=None, help="Date for reports (YYYY-MM-DD, default: today)")
@click.option("--reports-dir", "-r", default=None, type=click.Path(exists=True, path_type=Path))
def context(date: str | None, reports_dir: Path | None) -> None:
    """Output full PM context for an interactive session.

    Prints the system prompt, latest reports, registry, and memory
    so you can paste it into a Claude conversation.
    """
    if reports_dir is None:
        reports_dir = DEFAULT_REPORTS_DIR

    prompts_dir = Path(__file__).resolve().parent / "prompts"

    # System prompt
    system_prompt = (prompts_dir / "pm-system.md").read_text().strip()

    # Reports
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    reports = load_reports(reports_dir, date=date)

    # Registry + memory
    registry = load_registry_text()
    memory = load_memory()

    # Assemble
    click.echo("# PM System Prompt\n")
    click.echo(system_prompt)
    click.echo("\n---\n")
    click.echo("# Scout Reports\n")
    if reports:
        click.echo(json.dumps(reports, indent=2))
    else:
        click.echo("(No reports found for today. Run `beekeeper scout` first.)")
    click.echo("\n---\n")
    click.echo("# Project Registry\n")
    click.echo(registry or "(No registry found at ~/.beekeeper/projects.toml)")
    click.echo("\n---\n")
    click.echo("# PM Memory\n")
    click.echo(memory or "(No memory file found at ~/.beekeeper/memory.md)")
    click.echo("\n---\n")
    click.echo("You are now in an interactive PM session. The developer can discuss priorities,")
    click.echo("ask for advice, and you can suggest edits to ~/.beekeeper/memory.md")
    click.echo("and ~/.beekeeper/projects.toml to reflect evolving priorities.")


@cli.command()
def init() -> None:
    """Initialize ~/.beekeeper/ with example config files.

    Copies example templates for projects.toml and memory.md into
    ~/.beekeeper/. Will not overwrite existing files.
    """
    examples_dir = Path(__file__).resolve().parents[1] / ".." / "examples"
    # Resolve to handle the ..
    examples_dir = examples_dir.resolve()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    for filename in ("projects.toml", "memory.md"):
        src = examples_dir / filename
        dest = STATE_DIR / filename
        if dest.exists():
            click.echo(f"  {dest} already exists, skipping")
        elif not src.exists():
            click.echo(f"  Example template {src} not found, skipping")
        else:
            shutil.copy2(src, dest)
            click.echo(f"  Created {dest}")
            copied += 1

    if copied:
        click.echo(f"\nInitialized {STATE_DIR}. Edit the files to match your projects.")
    else:
        click.echo(f"\n{STATE_DIR} already configured. Nothing to do.")
