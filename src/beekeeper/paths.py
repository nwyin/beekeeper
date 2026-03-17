"""Canonical paths for beekeeper state."""

from pathlib import Path

STATE_DIR = Path.home() / ".beekeeper"
DEFAULT_MEMORY_PATH = STATE_DIR / "memory.md"
DEFAULT_REGISTRY_PATH = STATE_DIR / "projects.toml"
DEFAULT_REPORTS_DIR = STATE_DIR / "reports"
