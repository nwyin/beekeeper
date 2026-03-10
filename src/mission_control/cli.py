"""CLI entry point for mission-control."""

from __future__ import annotations

import logging
from pathlib import Path

import click

from mission_control.registry import load_registry
from mission_control.scout import save_report, scout_project

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

    for name, config in targets.items():
        try:
            report = scout_project(config)
            path = save_report(report, base_dir=output_dir)
            click.echo(f"[{name}] Report saved to {path}")
        except Exception:
            logger.exception("Failed to scout %s", name)
            click.echo(f"[{name}] FAILED (see logs)")
