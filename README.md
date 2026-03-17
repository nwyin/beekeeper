# beekeeper

Automated portfolio health monitoring. Scouts your projects nightly, synthesizes findings into an Obsidian daily note.

## Setup

```bash
cd beekeeper
uv sync
```

## Usage

### Manual run (scout all projects + write daily note)

```bash
uv run beekeeper run
```

### Scout a single project

```bash
uv run beekeeper scout --project my-cli-tool
```

### Synthesize existing reports into a daily note

```bash
uv run beekeeper synthesize
```

### Options

```
beekeeper run
  --vault, -V       Obsidian vault path (default: ~/notes)
  --target-date, -t Target daily note date, YYYY-MM-DD (default: today)
  --registry, -r    Path to projects.toml (default: repo root)

beekeeper scout
  --project, -p     Scout a specific project (default: all)
  --output-dir, -o  Reports output directory (default: reports/)
  --registry, -r    Path to projects.toml

beekeeper synthesize
  --reports-dir, -r Reports directory
  --vault, -V       Obsidian vault path
  --date, -d        Date to read reports from (default: today)
  --target-date, -t Target daily note date (default: today)
```

## Cron

Nightly run at 11pm:

```bash
./scripts/install-cron.sh
```

Logs to `logs/cron.log`. Verify with `crontab -l`.

## What it checks

Per project, the scout collects:

- **Git**: last commit date, staleness, uncommitted changes, branch count
- **GitHub** (via `gh`): open issues, open PRs, CI status, stars, forks
- **Dependencies**: outdated deps (cargo outdated / uv pip list --outdated / bun outdated)

Checks gracefully skip if tools are missing (e.g. `cargo-outdated` not installed).

## Output

Appends a `## Beekeeper` section to the Obsidian daily note with:

- Overview (project count, critical items)
- Action items (stale repos, CI failures, open issues/PRs, outdated deps, uncommitted changes)
- Per-project status summary

Re-running is idempotent -- the section is replaced, not duplicated.

## Project registry

All projects are registered in `projects.toml` with tier, priority, stack, and done criteria. See the file for the full list.

## Tests

```bash
uv run pytest -v
```
