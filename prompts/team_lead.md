# Team-lead report — generation instructions

You are generating a per-team activity report for the **team lead audience**. Your input is `metrics.json` in the current run directory. Your output is one `team_lead_<team>.docx` per team (Word format — easier to share than markdown). Charts are embedded directly into the docx; no separate output files are needed.

Use **python-docx** for the document and **matplotlib** for the charts. Both are installed in this project's venv via the `[report]` extra. If a dependency is missing, `uv pip install <pkg>` in the project venv before continuing.

## Audience

The team lead reads this before a 1:1 or retro. They know the team, they know the people, they know the work. They do **not** need a primer on what their team does — they need patterns they might have missed and questions worth asking.

## Calendar data — all-day events are split out

Each member in `metrics.json` has two calendar lists under `raw`:

- `busy_blocks_by_member` — **regular meetings only**. Use these for meeting hours, focus blocks, fragmentation, after-hours.
- `all_day_blocks_by_member` — **all-day events** (PTO, OOO, holidays, offsites). Detected via midnight-aligned local boundaries. Useful for surfacing PTO context (e.g. "alice took 8 days off in Q1, which explains her lower PR count") — never count them as meetings.

The pre-computed per-person calendar metrics already exclude all-day events.

## PR state semantics — read this first

Each PR in `metrics.json` has three timestamp fields that determine its state:

| state | `merged_at` | `closed_at` | meaning |
|---|---|---|---|
| merged | set | set (= merged_at) | merged successfully |
| abandoned | null | set | closed without merging — abandoned / superseded / rejected |
| open | null | null | still open at data-collection time |

**Implications for analysis:**

- **Cycle-time / time-to-merge / TTM percentiles** apply only to merged PRs. Always filter on `merged_at is not None`.
- **"Long-running" PR tables** must never include abandoned PRs labelled as "open." Surface abandoned PRs in a separate section if they're interesting.
- **Currently-open PRs** (both null) have an `age = now - created_at`. Surface separately when relevant; never mix into merged-PR cycle-time tables.

## Required structure (one file per team)

1. **Summary** — 4–8 bulleted observations specific to this team. Cite numbers. Lead with anything that changed period-over-period if multiple periods are in the data.
2. **Team metrics** — table of headline metrics for this team across all periods in the run (so the period column shows the trend). Cycle-time stats filtered to merged PRs.
3. **Per-person breakdown** — table per period: PRs authored (split: merged / abandoned / still-open), PRs reviewed, comments left, median cycle time (merged), time-to-first-review p50, mean reviews-on-their-PRs, mean commits/PR, 0-review-merge %, pending-review-at-merge %, meeting hours/week, focus hours/week. One row per member.
4. **Cycle time** — histogram + CDF of the team's **merged** PRs (latest period). If multiple periods, overlay them or stack them.
5. **Cycle time vs PR size** — bucket the team's merged PRs (XS/S/M/L/XL by lines changed) and show median TTM per bucket. Note if the team has many XL PRs.
6. **Review process** — review-iteration distribution (0, 1, 2, 3, 4, 5+) for the team's merged PRs. Pending-review-at-merge per person (worth flagging if any member is consistently above team average).
7. **Long-running PRs** — top 5 longest-cycle-time merged PRs for the team in the latest period, with PR number, days to merge, reviews, commits, author, title, URL. If there are any abandoned PRs in the window, surface them in a separate small sub-table titled "Abandoned PRs in window." If there are notable still-open PRs, surface in a third sub-table titled "Still-open PRs."
8. **Calendar load** — per-person meeting hours/week and focus-block hours/week. Flag asymmetric load.
9. **Period-over-period changes** (only if 2+ periods in the data) — table showing key metric deltas per person and team-level. Focus on direction, not absolute.
10. **Patterns worth discussing** — 3–5 short paragraphs framed as questions or hypotheses for a 1:1 / retro. Not judgments.

## Hard constraints

- **Cite specific numbers**, always.
- **Median over mean** for cycle time / size / count distributions.
- **Per-person callouts OK** here, since the audience already knows the team. But framing should be context, not scoring ("alice's review latency rose 40% — worth asking if her load shifted") rather than ranking ("alice is the slowest reviewer").
- **Period-over-period is the most reliable signal** — same team, same work mix.
- **Bot-strip before comparing** — if the team has any bot authors, report counts both with and without bots.
- **Filter to merged PRs for every TTM-based stat.** Closed-not-merged PRs are NOT long-running open PRs.

## Visual style

- matplotlib, log scales where appropriate, consistent colors per person within this team's report. Embed charts directly into the docx via `doc.add_picture()` at ~6 inches (render to `BytesIO` or a tempfile; no separate `charts/` directory).

## Document formatting (python-docx)

- `doc.add_heading()` for headings (level 1 title, level 2 sections, level 3 subsections).
- `doc.add_table()` for tables. Use a clean grid style; bold header rows.
- `doc.add_picture()` for charts.
- Save as `team_lead_<team>.docx` in the run directory.

## v1 data limitation to be aware of

The `reviews_given` and `comments_left` lists in `metrics.json` capture activity by **team members on PRs by other team members or outside the team**. The `prs[].reviews` field on each PR captures **all reviews on that PR, regardless of reviewer**. Use the right source for the right question:

- Team-internal review density → derive from `prs[].reviews` filtered to team members.
- Where team members spent their reviewing time outside the team → use `reviews_given`.
- Reviewer concentration on team's PRs → derive from `prs[].reviews`.

## When the run includes multiple periods

The structure above is designed for multi-period runs. Use the period-over-period section as the main vehicle for "what changed." If only one period is present, omit that section silently.

## When something is unclear

If a person has very few PRs in a period, sample-size warnings are appropriate. Don't draw conclusions from n=2.
