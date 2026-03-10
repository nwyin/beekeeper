# Mission Control

Automated portfolio health monitoring system that scouts all registered projects nightly, synthesizes findings into Obsidian daily notes, and creates Linear backlog issues for actionable items.

## Architecture

```
cron (11pm) → scout.py (per-project) → reports/*.json
           → synthesize.py → Obsidian daily note (append)
                           → Linear API (create backlog issues)
```

## Requirements

### Phase 1: Foundation + Scout

1. Python 3.12 project at `~/projects/mission-control` using `uv` with `pyproject.toml`
2. Project registry in `projects.toml` at repo root with this schema per project:
   ```toml
   [projects.dw2md]
   path = "/Users/tau/projects/dw2md"
   github = "tnguyen21/dw2md"
   tier = "ship"              # ship | build | research | support
   priority = "high"          # high | medium | low
   stack = "rust"             # rust | python | typescript | markdown
   done_criteria = "Published on crates.io, CI green, <5 open issues"
   promote_channels = ["hn", "reddit", "x", "blog"]
   ```
3. Scout module (`mission_control/scout.py`) that, given a project config, collects:
   - **Git**: last commit date, days since last commit, uncommitted changes (bool), number of local branches, current branch name
   - **GitHub** (via `gh` CLI subprocess calls): open issue count, open PR count, latest CI/workflow status (pass/fail/none), star count, fork count
   - **Dependencies**: outdated dependency list. Detection method per stack:
     - Rust: `cargo outdated --root-deps-only` (requires cargo-outdated)
     - Python: `uv pip list --outdated` (inside project venv)
     - TypeScript: `bun outdated`
   - Gracefully skip any check that fails (e.g., no `cargo-outdated` installed) and note it in the report
4. Scout output is a JSON file per project written to `reports/YYYY-MM-DD/project-name.json` with all collected data plus a `scouted_at` ISO timestamp
5. CLI entry point: `mission-control scout [--project NAME]` — scouts one project or all if no name given
6. Register dw2md as the first project in `projects.toml` with:
   - path: `/Users/tau/projects/dw2md`
   - github: `tnguyen21/dw2md`
   - tier: `ship`
   - priority: `high`
   - stack: `rust`

### Phase 2: Synthesizer + Obsidian Output

7. Synthesizer module (`mission_control/synthesize.py`) that:
   - Reads all JSON reports from `reports/YYYY-MM-DD/`
   - Generates a narrative markdown summary: 2-3 sentence overview, then per-project bullets with context
   - Identifies actionable items (stale repos, open issues needing response, outdated deps, failing CI)
8. Obsidian writer (`mission_control/obsidian.py`) that:
   - Target vault: `/Users/tau/projects/notes`
   - Target file: `dailies/YYYY-MM-DD.md` (tomorrow's date, since cron runs at 11pm)
   - If the daily note file doesn't exist, create it with a minimal template:
     ```markdown
     ---
     date: YYYY-MM-DD
     tags: [daily]
     ---
     ```
   - Append a `## Mission Control` section at the end of the file with the synthesized report
   - Idempotent: if `## Mission Control` section already exists, replace it rather than duplicating
9. CLI entry point: `mission-control synthesize` — reads today's reports, writes obsidian note

### Phase 3: Linear Integration

10. Linear client module (`mission_control/linear_client.py`) that:
    - Uses the Linear GraphQL API (https://api.linear.app/graphql)
    - Authenticates via `LINEAR_API_KEY` environment variable
    - Can create issues in a specified project as unassigned backlog items
    - Can list existing issues to avoid creating duplicates (match by title)
11. On each synthesize run, for every actionable item identified:
    - Check if a Linear issue with a matching title already exists in that project (dedup)
    - If not, create it as an unassigned backlog issue with:
      - Title: concise description (e.g., "dw2md: bump reqwest 0.11 → 0.12")
      - Description: context from the scout report
      - Project: matching the project name (create the Linear project if it doesn't exist)
      - Labels: auto-apply "mission-control" label (create if needed)
    - Include a summary of created issues in the Obsidian note
12. CLI entry point: `mission-control linear-sync` — can be run standalone to push today's actionable items to Linear

### Phase 4: Cron + Full Registry

13. Cron setup script (`scripts/install-cron.sh`) that installs a crontab entry:
    ```
    0 23 * * * cd /Users/tau/projects/mission-control && /Users/tau/projects/mission-control/.venv/bin/mission-control run >> /Users/tau/projects/mission-control/logs/cron.log 2>&1
    ```
14. `mission-control run` command that executes the full pipeline: scout all → synthesize → linear-sync
15. Register all projects in `projects.toml`:
    - dw2md (ship/high/rust)
    - slop-guard-rs (ship/high/rust)
    - pycfg-rs (ship/high/rust)
    - pycg-rs (ship/high/rust)
    - nailbook (build/high/typescript)
    - takeoff-protocol (build/medium/typescript)
    - hive (build/medium/python)
    - aisafety (research/high/python)
    - p5-nerdsnipe (research/low/python)
    - nwyin.com (support/medium/python)
    - cheerleader (support/low/python)
    - labrat (support/low/python)
    - notes (support/low/markdown)
    - agent-brain (support/low/markdown)
16. Logging: all runs append to `logs/YYYY-MM-DD.log` with timestamps

## Constraints

- All subprocess calls (gh, cargo, git) must have timeouts (30s default) so a hung command doesn't block the entire run
- Scout must be resilient: if one project's scout fails, log the error and continue to the next project
- No LLM calls in v0. The synthesizer uses deterministic logic and templates for the narrative. We can add an LLM summarization pass later.
- Linear API calls must be idempotent — never create duplicate issues for the same finding
- The `## Mission Control` section in Obsidian must be idempotent — re-running replaces, not appends
- No emoji in output (per user preference)
- Use `ruff` for linting/formatting (line-length=144)
- Dependencies should be minimal: `httpx` for Linear API, `tomli` for TOML parsing, `click` or `typer` for CLI

## Verification

- `uv run pytest` — all tests pass
- `uvx ruff check src/` — no lint errors
- `uvx ruff format --check src/` — properly formatted
- `uv run mission-control scout --project dw2md` — produces a valid JSON report in reports/
- `uv run mission-control synthesize` — appends section to Obsidian daily note
- `uv run mission-control linear-sync` — creates at least one Linear backlog issue (if actionable items exist)
- `uv run mission-control run` — full pipeline completes without error

## Success Criteria

- All verification commands pass
- Running `mission-control scout --project dw2md` produces `reports/YYYY-MM-DD/dw2md.json` with git, github, and dependency data
- Running `mission-control synthesize` appends a `## Mission Control` section to `/Users/tau/projects/notes/dailies/YYYY-MM-DD.md` with a narrative summary
- Running `mission-control linear-sync` creates an unassigned backlog issue in the `nwyin` Linear workspace (if actionable items found)
- Running `mission-control run` executes the full pipeline end-to-end
- Cron is installable via `scripts/install-cron.sh` and runs at 11:00 PM nightly
- Re-running is safe: no duplicate Obsidian sections, no duplicate Linear issues

---

## Spec 1: Foundation + Scout

### Requirements

- Items 1-6 from above
- Project structure with `pyproject.toml`, `src/mission_control/` package layout
- Unit tests for scout data collection (mock subprocess calls)
- Integration test that runs scout against dw2md (real git/gh calls)

### Success Criteria

- All verification commands pass (pytest, ruff check, ruff format)
- `uv run mission-control scout --project dw2md` produces valid JSON
- Scout gracefully handles missing tools (e.g., cargo-outdated not installed)

### Ralph Command

```
/ralph-loop:ralph-loop "Read /Users/tau/projects/mission-control/SPEC.md, implement Spec 1 (items 1-6). Use uv for env management, Python 3.12, src layout. Register dw2md in projects.toml." --max-iterations 30 --completion-promise "uv run pytest passes, uvx ruff check passes, uv run mission-control scout --project dw2md produces valid JSON"
```

---

## Spec 2: Synthesizer + Obsidian Output

### Prerequisites

- Spec 1 complete (scout produces JSON reports)

### Requirements

- Items 7-9 from above
- Unit tests for synthesizer logic and obsidian writer (mock filesystem)
- Integration test that runs synthesize against real scout output and writes to a temp directory

### Success Criteria

- All verification commands pass
- `uv run mission-control synthesize` produces a well-formatted markdown section
- Obsidian writer creates file if missing, appends if exists, replaces if section already present

### Ralph Command

```
/ralph-loop:ralph-loop "Read /Users/tau/projects/mission-control/SPEC.md, implement Spec 2 (items 7-9). Synthesizer reads scout JSON, generates narrative markdown, writes to Obsidian daily note." --max-iterations 25 --completion-promise "uv run pytest passes, uv run mission-control synthesize produces valid Obsidian output"
```

---

## Spec 3: Linear Integration

### Prerequisites

- Spec 2 complete (synthesizer identifies actionable items)

### Requirements

- Items 10-12 from above
- Unit tests for Linear client (mock HTTP responses)
- Integration test requires LINEAR_API_KEY env var (skip if not set)

### Success Criteria

- All verification commands pass
- `uv run mission-control linear-sync` creates issues in Linear (when API key is set)
- Duplicate detection works (running twice doesn't create duplicate issues)

### Ralph Command

```
/ralph-loop:ralph-loop "Read /Users/tau/projects/mission-control/SPEC.md, implement Spec 3 (items 10-12). Linear GraphQL client with httpx, dedup by title, create unassigned backlog issues." --max-iterations 25 --completion-promise "uv run pytest passes, Linear client unit tests pass with mocked responses"
```

---

## Spec 4: Cron + Full Registry

### Prerequisites

- Specs 1-3 complete

### Requirements

- Items 13-16 from above
- `mission-control run` command chains scout → synthesize → linear-sync
- Install script for cron
- All 14 projects registered in projects.toml

### Success Criteria

- All verification commands pass
- `uv run mission-control run` completes full pipeline
- `scripts/install-cron.sh` installs valid crontab entry
- All projects in registry have valid config

### Ralph Command

```
/ralph-loop:ralph-loop "Read /Users/tau/projects/mission-control/SPEC.md, implement Spec 4 (items 13-16). Add run command, cron install script, register all 14 projects." --max-iterations 20 --completion-promise "uv run pytest passes, uv run mission-control run completes without error"
```
