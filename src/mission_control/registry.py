"""Project registry: loads and validates projects.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

VALID_TIERS = {"ship", "build", "research", "support"}
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_STACKS = {"rust", "python", "typescript", "markdown"}


@dataclass
class ProjectConfig:
    name: str
    path: Path
    github: str | None = None
    tier: str = "support"
    priority: str = "medium"
    stack: str = "markdown"
    done_criteria: str = ""
    promote_channels: list[str] = field(default_factory=list)


def load_registry(registry_path: Path | None = None) -> dict[str, ProjectConfig]:
    if registry_path is None:
        registry_path = Path(__file__).resolve().parents[2] / "projects.toml"

    with open(registry_path, "rb") as f:
        data = tomllib.load(f)

    projects: dict[str, ProjectConfig] = {}
    for name, cfg in data.get("projects", {}).items():
        projects[name] = ProjectConfig(
            name=name,
            path=Path(cfg["path"]).expanduser(),
            github=cfg.get("github"),
            tier=cfg.get("tier", "support"),
            priority=cfg.get("priority", "medium"),
            stack=cfg.get("stack", "markdown"),
            done_criteria=cfg.get("done_criteria", ""),
            promote_channels=cfg.get("promote_channels", []),
        )
    return projects
