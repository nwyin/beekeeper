# Project Context — beekeeper

## Overview
Automated portfolio health monitor that nightly scouts registered projects (git, GitHub, deps), synthesizes findings via an LLM (Claude), and writes an actionable briefing into an Obsidian daily note.

## Architecture
- **registry** (`registry.py`) — Loads `projects.toml` (TOML) into `ProjectConfig` dataclasses. Config lives at `~/.beekeeper/projects.toml` (canonical) with a repo-root copy used by tests.
- **scout** (`scout.py`) — Collects git, GitHub (via `gh` CLI), and dependency (cargo/uv/bun) health data per project. Runs all three collectors in parallel via `ThreadPoolExecutor`. Outputs `ScoutReport` dataclass serialized to `reports/YYYY-MM-DD/<project>.json`.
- **synthesize** (`synthesize.py`) — Reads day's JSON reports, generates per-project markdown summaries, extracts action items (stale, CI fail, open issues/PRs, outdated deps), produces a `SynthesisResult`.
- **llm** (`llm.py`) — Calls Anthropic API (Claude) with system+user prompt templates from `src/prompts/` to generate a PM-style analysis. Injected into `SynthesisResult.llm_analysis`.
- **obsidian** (`obsidian.py`) — Writes/replaces a `## Beekeeper` section in an Obsidian daily note (`vault/dailies/YYYY-MM-DD.md`). Idempotent via regex replacement.
- **memory** (`memory.py`) — Read/append timestamped memos to `~/.beekeeper/memory.md`, organized by sections (Strategic Goals, Current Focus, Project Notes, Decisions).
- **cli** (`cli.py`) — Click CLI with commands: `scout`, `synthesize`, `run` (full pipeline), `memo`, `context`, `init`. The `run` command parallelizes scouting (6 workers), then synthesizes + writes daily note.
- **Data flow**: `cron (nightly) -> cli run -> scout all projects in parallel -> JSON reports -> synthesize -> LLM analysis -> Obsidian daily note`

## Key Files
- `src/beekeeper/cli.py` — CLI entry point; all commands defined here
- `src/beekeeper/scout.py` — Per-project health data collection (git/GitHub/deps)
- `src/beekeeper/synthesize.py` — Report aggregation, action item extraction, markdown rendering
- `src/beekeeper/llm.py` — Anthropic API client for PM analysis generation
- `src/beekeeper/obsidian.py` — Obsidian daily note writer (idempotent section replacement)
- `src/beekeeper/memory.py` — PM memory read/append with section-aware insertion
- `src/beekeeper/registry.py` — TOML registry loader -> ProjectConfig dataclasses
- `src/beekeeper/paths.py` — Canonical paths (`~/.beekeeper/` state dir, reports, memory, registry)
- `src/beekeeper/prompts/pm-system.md` — System prompt for LLM analysis (PM persona, attention levels, dispatch rules)
- `src/beekeeper/prompts/pm-user.md` — User prompt template (reports + registry + memory injection)
- `projects.toml` — Repo-root project registry (example projects with type/attention/stack/promote_channels)
- `scripts/install-cron.sh` — Crontab installer (runs nightly, sources `~/.beekeeper/.env`)
- `tests/test_integration.py` — End-to-end tests (scout -> synthesize -> daily note)
- `tests/test_scout.py` — Unit tests for scout module with mocked subprocess calls

## Build & Test
- **Language**: Python >=3.12
- **Package manager**: `uv` — install with `uv sync --dev`
- **Build**: `uv build` (uses `uv_build` backend)
- **Test**: `uv run pytest`
- **Lint**: `uvx ruff check src/`
- **Format**: `uvx ruff format src/` (line-length=144)
- **Type check**: N/A (no mypy/pyright configured; `py.typed` marker exists)
- **Pre-commit**: N/A
- **Quirks**: Integration tests make real `git` and `gh` CLI calls against actual repos on disk. They use `tmp_path` for output but depend on `~/.beekeeper/projects.toml` existing with valid project paths. The `--no-llm` flag or missing `ANTHROPIC_API_KEY` skips LLM calls in synthesize. Default state dir is `~/.beekeeper/`, not the repo itself.

## Conventions
- `from __future__ import annotations` in every module
- Dataclasses for all data structures (no Pydantic, no TypedDict)
- `subprocess.run` with 30s timeout for all external CLI calls; errors caught per-call, never fatal
- Click for CLI with `@click.group()` pattern; subcommands are `@cli.command()`
- Logging via `logging.getLogger(__name__)`; no print statements in library code
- Path handling via `pathlib.Path` throughout; no `os.path`
- Tests organized by module (test_scout.py mirrors scout.py); use `tmp_path` fixture for isolation
- Mocking via `unittest.mock.patch` on internal `_run` helper, not on `subprocess.run` directly
- snake_case everywhere; files named after their module concept
- No emoji in output

## Dependencies & Integration
- **anthropic** (>=0.52) — LLM calls for PM analysis; model defaults to `claude-opus-4-6`, overridable via `BEEKEEPER_LLM_MODEL` env var
- **click** (>=8.1) — CLI framework
- **gh** CLI — GitHub data (issues, PRs, CI status, stars/forks); called as subprocess
- **git** CLI — Local repo health (last commit, branches, uncommitted changes); called as subprocess
- **cargo-outdated** / **uv pip list --outdated** / **bun outdated** — Dependency freshness per stack
- **Obsidian vault** — Daily notes written to `dailies/YYYY-MM-DD.md` in the configured vault
- **Cron** — Scheduled via `scripts/install-cron.sh`; sources `~/.beekeeper/.env` for API keys
- **State directory** `~/.beekeeper/` — Contains `projects.toml`, `memory.md`, `reports/`, `logs/`

## Gotchas
- Two `projects.toml` locations: repo root (checked into git, used as default by `load_registry`) vs `~/.beekeeper/projects.toml` (defined in `paths.py` as `DEFAULT_REGISTRY_PATH`). The `load_registry` function defaults to the `~/.beekeeper/` path, but the `llm.py:load_registry_text` also reads from there. The repo-root copy may diverge.
- Integration tests hit real repos and real `gh` API — they will fail without network access or if referenced repos don't exist locally.
- `obsidian.py` defaults vault to `~/notes`; always pass `--vault` in tests.
- The `run` command always uses `DEFAULT_REPORTS_DIR` (`~/.beekeeper/reports/`), not the repo's `reports/` dir.
- Subprocess calls to `gh`, `git`, `cargo`, `uv`, `bun` can fail silently — errors are logged but don't halt the pipeline.
- STALENESS_THRESHOLD_DAYS is 14 days in `synthesize.py`; this is the threshold for flagging a project as stale.
- The cron script sources `~/.beekeeper/.env` which must contain `ANTHROPIC_API_KEY` for LLM analysis to run.
