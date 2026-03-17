"""Project registry: loads and validates projects.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from beekeeper.paths import DEFAULT_REGISTRY_PATH

VALID_TYPES = {"tool", "app", "research", "content"}
VALID_ATTENTION = {"focus", "maintain", "explore", "habit", "shelved"}
VALID_STACKS = {"rust", "python", "typescript", "markdown"}


@dataclass
class ProjectConfig:
    name: str
    path: Path
    github: str | None = None
    type: str = "tool"
    attention: str = "maintain"
    stack: str = "markdown"
    promote_channels: list[str] = field(default_factory=list)


def load_registry(registry_path: Path | None = None) -> dict[str, ProjectConfig]:
    if registry_path is None:
        registry_path = DEFAULT_REGISTRY_PATH

    with open(registry_path, "rb") as f:
        data = tomllib.load(f)

    projects: dict[str, ProjectConfig] = {}
    for name, cfg in data.get("projects", {}).items():
        projects[name] = ProjectConfig(
            name=name,
            path=Path(cfg["path"]).expanduser(),
            github=cfg.get("github"),
            type=cfg.get("type", "tool"),
            attention=cfg.get("attention", "maintain"),
            stack=cfg.get("stack", "markdown"),
            promote_channels=cfg.get("promote_channels", []),
        )
    return projects
