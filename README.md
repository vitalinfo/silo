# silo

Team and person velocity / contribution analysis from GitHub + Google Calendar.

silo collects pull requests (with reviews, commits, pending requests), comments,
and busy-time intervals over configurable periods, aggregates them into per-person
and per-team metrics, and emits a single `metrics.json` plus an `INSTRUCTIONS.md`
pointer.

The actual report — markdown, tables, charts, narrative — is produced by **Cowork**
reading those files. Two report shapes are supported via tracked prompt templates:

- **Team-lead report** — per-person breakdown for one team, period delta, patterns for 1:1 / retro.
- **Exec report** — cross-team comparison, normalized metrics, charts, recommendations, explicit disclaimer.

silo is responsible for collection + serialization. Cowork is responsible for analysis + presentation. This split means:

- silo has no LLM dependency, no chart library, no template engine. Tiny surface, easy to extend.
- Report shape is editable as plain markdown in `prompts/` — no code change to tune what gets generated.
- Cowork uses your existing subscription; no separate Anthropic API key needed.

## What gets collected

| Source | Field | Notes |
|---|---|---|
| GitHub PRs (authored by team) | title, url, author, created/merged/closed, additions, deletions, commits count, pending review requests at merge, all reviews on the PR, bot flag | via GraphQL, multi-org, paginated |
| GitHub reviews (by team members) | state, submitted_at, body length, reviewer, PR ref | the "what did this person review outside their own PRs" set |
| GitHub comments (by team members) | author, created_at, body length, PR ref | top-level PR comments only (not inline) |
| Google Calendar | busy intervals per member | freebusy API; no event titles, no attendees. All-day events (PTO / OOO / holidays / offsites) are detected by their midnight-aligned local boundaries and surfaced separately so they don't inflate meeting/focus metrics. |

All raw records are cached locally in `.cache/silo.sqlite` so re-runs over the
same window are near-instant.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv venv --python 3.11
uv pip install -e ".[dev]"
cp .env.example .env
cp config/teams.example.yaml config/teams.yaml
cp config/run.example.yaml config/run.yaml
```

`config/teams.yaml`, `config/run.yaml`, and `.env` are gitignored — only the
`*.example.yaml` templates are tracked. Edit the copies, not the templates.

### `.env` values

```
GITHUB_TOKEN=ghp_...                  # classic PAT, scopes: repo + read:org
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
```

No Anthropic key needed — narrative generation runs through Cowork.

**GitHub token** — use a **classic PAT** (Settings → Developer settings → Personal
access tokens → *Tokens (classic)*). Fine-grained PATs are locked to a single
resource owner, which doesn't work across multiple orgs. Scopes: `repo` + `read:org`.
If any org enforces SAML SSO, "Configure SSO" next to the token and authorize each org.

**Google OAuth** — In [Google Cloud Console](https://console.cloud.google.com/):
1. Create or reuse a project.
2. Enable the **Google Calendar API**.
3. Credentials → Create OAuth client ID → **Desktop app**. Copy ID + secret into `.env`.
4. First run pops a browser tab for consent. Refresh token caches at `~/.config/silo/google_token.json`.

Freebusy works against any calendar shared via Workspace default settings — true
for most orgs. If yours blocks it, calendar metrics will be empty and only GitHub
data is meaningful.

## Configuration

### `config/teams.yaml`

```yaml
github_orgs:
  - your-primary-org
  - your-secondary-org

teams:
  - name: backend
    lead: alice@example.com
    members:
      - github: alice-gh
        google: alice@example.com
        tz: "America/New_York"   # IANA name; defaults to UTC if omitted
      - github: bob-gh
        google: bob@example.com
        tz: "Europe/Kyiv"
```

People can contribute across any listed org; the collector merges results.

**Per-member timezone** lets the calendar load metrics (focus blocks, after-hours)
be computed against each person's local workday. The `work_hours` shape itself
(start/end/workdays) is shared across the team.

**Bots / service accounts**: list them as members with `github: dependabot[bot]`
and omit `google`. Their PRs are collected (so throughput counts are accurate)
but calendar-derived metrics are skipped. Each PR also has an `is_bot` flag in
the JSON, derived from the `[bot]` suffix on the GitHub login.

### `config/run.yaml`

```yaml
periods:
  - label: Q1
    from: 2026-01-01
    to: 2026-03-31
  - label: Q2_so_far
    from: 2026-04-01
    to: 2026-05-13

teams: all                       # or [backend, frontend]
comparisons:
  period_over_period: true
  cross_team: true
reports: [team_lead, exec]       # which prompt templates to surface in INSTRUCTIONS.md

work_hours:
  start: "09:00"
  end: "18:00"
  workdays: [mon, tue, wed, thu, fri]
```

## Running

### 1. Collect data + write the JSON

```bash
.venv/bin/silo                 # uses config/teams.yaml + config/run.yaml
.venv/bin/silo --no-cache      # force fresh fetch
```

This writes:

```
reports/<timestamp>/
├── metrics.json           # all raw + aggregated data
└── INSTRUCTIONS.md        # pointer for Cowork to follow
```

### 2. Generate the actual report in Cowork

Open the silo project in Cowork (or any Claude Code session in this directory) and ask:

> Follow `reports/<timestamp>/INSTRUCTIONS.md`.

Cowork reads the instructions + `metrics.json`, follows the prompt template (e.g.
`prompts/exec.md`), generates matplotlib charts, and writes a **Word (`.docx`)**
report into the same directory. Word format was picked over markdown because it's
easier to share with non-developer audiences.

Cowork uses `python-docx` and `matplotlib` for this. Install them once:

```bash
uv pip install -e ".[dev,report]"
```

### Smoke tests for the collectors

Before a full run, confirm each collector against real credentials:

```bash
.venv/bin/python scripts/smoke_github.py YOUR_GH_HANDLE
.venv/bin/python scripts/smoke_github.py YOUR_GH_HANDLE 60          # last 60 days
.venv/bin/python scripts/smoke_github.py YOUR_GH_HANDLE --no-cache

.venv/bin/python scripts/smoke_calendar.py you@yourcompany.com
.venv/bin/python scripts/smoke_calendar.py coworker@yourcompany.com
```

The smokes log one line per query so progress is visible.

## Caching

`.cache/silo.sqlite` keys raw records by `(source, entity, from_date, to_date)`.
Re-running over the same window is near-instant. To bypass:

```bash
.venv/bin/silo --no-cache
```

Or delete `.cache/silo.sqlite`.

## Project layout

```
silo/
├── config/
│   ├── teams.example.yaml      # template; copy to teams.yaml (gitignored)
│   └── run.example.yaml        # template; copy to run.yaml (gitignored)
├── prompts/
│   ├── exec.md                 # Cowork instructions for the exec report
│   └── team_lead.md            # Cowork instructions for the team-lead report
├── src/silo/
│   ├── config.py               # Pydantic schemas for both yamls
│   ├── cache.py                # SQLite-backed raw-record cache
│   ├── collectors/
│   │   ├── github.py           # GraphQL: PRs, reviews, comments
│   │   ├── calendar.py         # OAuth + freebusy
│   │   └── _graphql.py         # tiny GraphQL client (httpx)
│   ├── metrics/                # pure-function metric implementations
│   ├── aggregate.py            # collectors → metrics → PeriodReport
│   ├── serialize.py            # PeriodReport + run config → metrics.json + INSTRUCTIONS.md
│   ├── types.py                # domain types
│   └── main.py                 # entrypoint
├── scripts/                    # smoke tests for each collector
└── tests/                      # pytest suite for metric math + serializer
```

## Development

```bash
.venv/bin/python -m pytest tests/ -v
```

## Design notes

- silo's contract: collect data → emit comprehensive JSON. No narrative, no charts, no opinions.
- Cowork is the analysis + presentation layer. Edit `prompts/*.md` to change the report shape; no Python change required.
- Cross-team comparison and ranking framing are controlled by the prompts, not by code. The defaults forbid rankings, require citing numbers, and include a "what this measures / does not measure" disclaimer.
- Each member supplies their own IANA timezone in `teams.yaml`. The `work_hours` wall-clock shape is shared across the team.
- The `prs[].reviews` list captures **all** reviews on a PR (not only by team members), so review-health metrics aren't restricted to internal-only reviews.
