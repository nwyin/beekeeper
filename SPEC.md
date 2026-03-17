# Beekeeper

Automated portfolio health monitoring system that scouts all registered projects nightly, synthesizes findings into Obsidian daily notes, and creates backlog issues for actionable items.

## Architecture

```
cron (nightly) → scout.py (per-project) → reports/*.json
               → synthesize.py → Obsidian daily note (append)
```

## Requirements

### Phase 1: Foundation + Scout

1. Python 3.12 project using `uv` with `pyproject.toml`
2. Project registry in `projects.toml` at repo root with this schema per project:
   ```toml
   [projects.my-cli-tool]
   path = "/home/user/projects/my-cli-tool"
   github = "username/my-cli-tool"
   type = "tool"              # tool | app | research | content
   attention = "focus"        # focus | maintain | explore | habit | shelved
   stack = "rust"             # rust | python | typescript | markdown
   promote_channels = ["hn", "reddit", "x", "blog"]
   ```
3. Scout module (`beekeeper/scout.py`) that, given a project config, collects:
   - **Git**: last commit date, days since last commit, uncommitted changes (bool), number of local branches, current branch name
   - **GitHub** (via `gh` CLI subprocess calls): open issue count, open PR count, latest CI/workflow status (pass/fail/none), star count, fork count
   - **Dependencies**: outdated dependency list. Detection method per stack:
     - Rust: `cargo outdated --root-deps-only` (requires cargo-outdated)
     - Python: `uv pip list --outdated` (inside project venv)
     - TypeScript: `bun outdated`
   - Gracefully skip any check that fails (e.g., no `cargo-outdated` installed) and note it in the report
4. Scout output is a JSON file per project written to `reports/YYYY-MM-DD/project-name.json` with all collected data plus a `scouted_at` ISO timestamp
5. CLI entry point: `beekeeper scout [--project NAME]` -- scouts one project or all if no name given

### Phase 2: Synthesizer + Obsidian Output

6. Synthesizer module (`beekeeper/synthesize.py`) that:
   - Reads all JSON reports from `reports/YYYY-MM-DD/`
   - Generates a narrative markdown summary: 2-3 sentence overview, then per-project bullets with context
   - Identifies actionable items (stale repos, open issues needing response, outdated deps, failing CI)
7. Obsidian writer (`beekeeper/obsidian.py`) that:
   - Target vault: configurable via `--vault` flag (default: `~/notes`)
   - Target file: `dailies/YYYY-MM-DD.md`
   - If the daily note file doesn't exist, create it with a minimal template:
     ```markdown
     ---
     date: YYYY-MM-DD
     tags: [daily]
     ---
     ```
   - Append a `## Beekeeper` section at the end of the file with the synthesized report
   - Idempotent: if `## Beekeeper` section already exists, replace it rather than duplicating
8. CLI entry point: `beekeeper synthesize` -- reads today's reports, writes obsidian note

### Phase 3: Cron + Full Registry

9. Cron setup script (`scripts/install-cron.sh`) that installs a crontab entry running `beekeeper run` nightly
10. `beekeeper run` command that executes the full pipeline: scout all -> synthesize -> write daily note
11. Register all projects in `projects.toml`
12. Logging: all runs append to `logs/YYYY-MM-DD.log` with timestamps

## Constraints

- All subprocess calls (gh, cargo, git) must have timeouts (30s default) so a hung command doesn't block the entire run
- Scout must be resilient: if one project's scout fails, log the error and continue to the next project
- No LLM calls in v0. The synthesizer uses deterministic logic and templates for the narrative. We can add an LLM summarization pass later.
- The `## Beekeeper` section in Obsidian must be idempotent -- re-running replaces, not appends
- No emoji in output
- Use `ruff` for linting/formatting (line-length=144)
- Dependencies should be minimal: `anthropic` for LLM, `click` for CLI

## Verification

- `uv run pytest` -- all tests pass
- `uvx ruff check src/` -- no lint errors
- `uvx ruff format --check src/` -- properly formatted
- `uv run beekeeper scout --project <name>` -- produces a valid JSON report in reports/
- `uv run beekeeper synthesize` -- appends section to Obsidian daily note
- `uv run beekeeper run` -- full pipeline completes without error

## Success Criteria

- All verification commands pass
- Running `beekeeper scout --project <name>` produces `reports/YYYY-MM-DD/<name>.json` with git, github, and dependency data
- Running `beekeeper synthesize` appends a `## Beekeeper` section to the configured vault's daily note
- Running `beekeeper run` executes the full pipeline end-to-end
- Cron is installable via `scripts/install-cron.sh` and runs nightly
- Re-running is safe: no duplicate Obsidian sections
