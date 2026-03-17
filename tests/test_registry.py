"""Tests for project registry loading."""

from pathlib import Path
from textwrap import dedent

from beekeeper.registry import ProjectConfig, load_registry


def test_load_registry_basic(tmp_path: Path) -> None:
    toml_file = tmp_path / "projects.toml"
    toml_file.write_text(
        dedent("""\
        [projects.myproject]
        path = "/tmp/myproject"
        github = "user/myproject"
        type = "tool"
        attention = "focus"
        stack = "rust"
        promote_channels = ["hn", "x"]
    """)
    )

    projects = load_registry(toml_file)
    assert "myproject" in projects
    p = projects["myproject"]
    assert isinstance(p, ProjectConfig)
    assert p.name == "myproject"
    assert p.path == Path("/tmp/myproject")
    assert p.github == "user/myproject"
    assert p.type == "tool"
    assert p.attention == "focus"
    assert p.stack == "rust"
    assert p.promote_channels == ["hn", "x"]


def test_load_registry_defaults(tmp_path: Path) -> None:
    toml_file = tmp_path / "projects.toml"
    toml_file.write_text(
        dedent("""\
        [projects.minimal]
        path = "/tmp/minimal"
    """)
    )

    projects = load_registry(toml_file)
    p = projects["minimal"]
    assert p.github is None
    assert p.type == "tool"
    assert p.attention == "maintain"
    assert p.stack == "markdown"
    assert p.promote_channels == []


def test_load_registry_multiple_projects(tmp_path: Path) -> None:
    toml_file = tmp_path / "projects.toml"
    toml_file.write_text(
        dedent("""\
        [projects.alpha]
        path = "/tmp/alpha"
        type = "tool"

        [projects.beta]
        path = "/tmp/beta"
        type = "research"
    """)
    )

    projects = load_registry(toml_file)
    assert len(projects) == 2
    assert "alpha" in projects
    assert "beta" in projects


def test_load_registry_empty(tmp_path: Path) -> None:
    toml_file = tmp_path / "projects.toml"
    toml_file.write_text("")

    projects = load_registry(toml_file)
    assert projects == {}
