# silo

Team and person velocity / contribution analysis from GitHub + Google Calendar.

Pulls PRs, reviews, comments (GitHub GraphQL) and busy-time intervals (Google
Calendar freebusy), aggregates them into per-person and per-team metrics over
configurable periods, and renders two markdown reports:

- **Team-lead report** — per-person detail for one team, period-over-period delta, narrative paragraphs.
- **Exec report** — team-level metrics only (no per-person), cross-team comparison on normalized metrics, narrative-led.

The narrative is generated via the Claude API. Metrics are framed as "patterns
worth discussing," not scores or rankings.

## What it measures

| Group | Metric | Used in |
|---|---|---|
| Flow | PR cycle time (p50/p90), time-to-first-review, PR size | both reports |
| Review health | Median review latency, reviewer concentration, % PRs with substantive review | both reports |
| Load | Meeting hours, focus-block hours, fragmentation, after-hours busy time | both reports (per-person in team-lead, team avg in exec) |
| Contribution | PRs authored / reviewed / comments left per person; within-team Gini | team-lead only |

The exec report deliberately omits per-person data and includes a "what this
measures / does not measure" disclaimer.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv venv --python 3.11
uv pip install -e ".[dev]"
cp .env.example .env
cp config/teams.example.yaml config/teams.yaml
cp config/run.example.yaml config/run.yaml
```

`config/teams.yaml`, `config/run.yaml`, and `.env` are all gitignored — only the
`*.example.yaml` templates are tracked. Edit the copies, not the templates.

### `.env` values

```
GITHUB_TOKEN=ghp_...                  # classic PAT, scopes: repo + read:org
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
ANTHROPIC_API_KEY=sk-ant-...
```

**GitHub token** — use a **classic PAT** (Settings → Developer settings → Personal
access tokens → *Tokens (classic)*). Fine-grained PATs are locked to a single
org, which doesn't work when analyzing across multiple orgs. Scopes needed:
`repo` + `read:org`. If any of your orgs enforces SAML SSO, click "Configure SSO"
next to the token and authorize each org.

**Google OAuth** — In [Google Cloud Console](https://console.cloud.google.com/):
1. Create a project (or use an existing one).
2. Enable the **Google Calendar API**.
3. Credentials → Create OAuth client ID → **Desktop app**. Copy the client ID and secret into `.env`.
4. First run of the calendar collector pops a browser tab for consent. The
   refresh token is cached at `~/.config/silo/google_token.json` and reused.

Freebusy works against any calendar in your Workspace that allows freebusy
sharing — which is the default for most orgs. If your org disables that, the
calendar half of the tool returns empty results and only the GitHub metrics
will be meaningful.

**Anthropic key** — used only for narrative generation in the renderers.

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

**Per-member timezone**: each member declares their IANA timezone. This is
used to interpret the `work_hours` wall-clock shape (e.g. 9–18) for that
specific person, so focus-block and after-hours metrics are computed against
the right local day. Defaults to `UTC` if omitted.

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
  period_over_period: true       # same team, different periods
  cross_team: true               # cross-team within the latest period
reports: [team_lead, exec]

work_hours:
  start: "09:00"
  end: "18:00"
  workdays: [mon, tue, wed, thu, fri]
  # Timezone is per-member (see teams.yaml). The wall-clock workday shape
  # here applies to everyone; each member's tz determines when those hours fall.
```

## Smoke tests

Before running a full report, confirm each collector works against your real
credentials:

```bash
.venv/bin/python scripts/smoke_github.py YOUR_GH_HANDLE
.venv/bin/python scripts/smoke_github.py YOUR_GH_HANDLE 60          # last 60 days
.venv/bin/python scripts/smoke_github.py YOUR_GH_HANDLE --no-cache  # force fresh

.venv/bin/python scripts/smoke_calendar.py you@yourcompany.com
.venv/bin/python scripts/smoke_calendar.py coworker@yourcompany.com
```

The smokes print one log line per GraphQL query so you can see progress.
Cached results are reused on re-runs unless `--no-cache` is passed.

## Running the report (coming next)

Once wired end-to-end:

```bash
.venv/bin/silo
```

Reads `config/teams.yaml` + `config/run.yaml`, collects data into
`.cache/silo.sqlite`, writes `reports/<timestamp>/team_lead.md` and
`reports/<timestamp>/exec.md`.

## Caching

All raw collector output is cached in `.cache/silo.sqlite`, keyed by
`(source, entity, from_date, to_date)`. Re-running a report over the same
window is near-instant. To force a fresh fetch:

```bash
.venv/bin/silo --no-cache
```

Or delete `.cache/silo.sqlite` entirely.

## Project layout

```
silo/
├── config/
│   ├── teams.example.yaml      # template; copy to teams.yaml (gitignored)
│   └── run.example.yaml        # template; copy to run.yaml (gitignored)
├── src/silo/
│   ├── config.py               # Pydantic schemas for both yamls
│   ├── cache.py                # SQLite-backed raw-record cache
│   ├── collectors/
│   │   ├── github.py           # GraphQL: PRs, reviews, comments
│   │   ├── calendar.py         # OAuth + freebusy
│   │   └── _graphql.py         # tiny GraphQL client (httpx)
│   ├── metrics/
│   │   ├── flow.py
│   │   ├── review_health.py
│   │   ├── load.py
│   │   ├── contribution.py
│   │   └── _stats.py           # percentile helper
│   ├── report/
│   │   ├── team_lead.py
│   │   ├── exec.py
│   │   └── narrative.py        # Claude API
│   ├── aggregate.py            # collectors → metrics → PeriodReport
│   └── main.py                 # entrypoint
├── scripts/
│   ├── smoke_github.py
│   └── smoke_calendar.py
└── tests/                      # pytest suite for metric math + config validation
```

## Development

```bash
.venv/bin/python -m pytest tests/ -v
```

## Design notes

- Cross-team comparison is restricted to normalized metrics (latency, ratios,
  per-week rates) so that teams with different work shapes aren't ranked unfairly.
- The team-lead report shows per-person tables; the exec report deliberately does not.
- Metrics are intentionally framed as discussion prompts in the narrative; no scores or rankings are produced.
- Each member supplies their own IANA timezone in `teams.yaml`; the `work_hours` shape (start/end/workdays) is shared across the team.
