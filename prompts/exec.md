# Exec report — generation instructions

You are generating a cross-team engineering activity report for a **CTO / VP audience**. Your input is `metrics.json` in the current run directory. Your output is `exec.docx` in the same directory (Word format — easier for execs to share over email/drive than markdown), with any charts saved under `charts/` and embedded into the doc.

Use **python-docx** for the document and **matplotlib** for the charts. Both are installed in this project's venv via the `[report]` extra. If a dependency is missing, `uv pip install <pkg>` in the project venv before continuing.

## Audience

CTOs and VPs read this to understand patterns across teams. They will compare teams in their heads regardless of how the data is presented, so framing matters: this report's job is to make those comparisons **fair and contextualized**, not to rank.

## PR state semantics — read this first

Each PR in `metrics.json` has three timestamp fields that determine its state:

| state | `merged_at` | `closed_at` | meaning |
|---|---|---|---|
| merged | set | set (= merged_at) | merged successfully |
| abandoned | null | set | closed without merging — abandoned / superseded / rejected |
| open | null | null | still open at data-collection time |

**This matters for every analysis that talks about "cycle time" or "longest-running":**

- **Cycle-time / time-to-merge metrics** only make sense for **merged** PRs. Always filter to `merged_at is not None` before computing cycle time, percentiles, or distributions.
- **"Long-tail / longest-running" tables** must not include abandoned PRs labelled as "open." If you want to surface abandoned PRs, do it in a separate "Abandoned PRs in window" section, clearly labelled.
- **Currently-open PRs** (both null) have an `age = now - created_at`. Surface separately if interesting; never mix into merged-PR cycle-time tables.

When in doubt, treat each PR-state class as its own population. **Do not pretend a closed-without-merge PR is "still open at day 263."**

## Required structure

Follow this section order. Section names can be tweaked but the order shouldn't change because the disclaimer needs to anchor the reader before deeper analysis.

1. **Executive summary** — 6–10 short bulleted findings, each citing specific numbers. Lead with the most surprising or actionable observations.
2. **Methodology & data** — one short paragraph: what was measured, source (GitHub PRs via GraphQL, Google Calendar freebusy), period(s), and any caveats from this run. Include a one-line note about how PR states are interpreted (see above).
3. **Headline comparison** — side-by-side table of the headline metrics for the latest period across all teams. Median over mean. Include human vs total PR counts (excluding bots). **Cycle-time stats: merged PRs only.**
4. **Volume & throughput** — chart of PRs/period per team, bot vs human split if relevant.
5. **Cycle time (merged PRs)** — distribution analysis. Histogram and CDF of time-to-merge per team. Cumulative merge bands (% merged within 1h, 1d, 3d, 1w, 30d). Boxplot on log scale if it adds clarity.
6. **Cycle time vs PR size** — bucket merged PRs into XS (<10), S (10–49), M (50–249), L (250–999), XL (≥1000) lines changed. Median TTM per bucket per team. Note where buckets flip.
7. **Review process** — review-iteration distribution (0, 1, 2, 3, 4, 5+) per team. Cycle time vs review count. Pending-review-at-merge rate (this is high-signal). % PRs with no recorded reviews.
8. **Commits per PR** — distribution + per-team mean/median. Long-tail callouts.
9. **Predictors of cycle time** — Pearson correlation between cycle time and: PR size, commit count, review count (merged PRs only). State which is the strongest predictor and why it matters.
10. **Work composition** — title-prefix classification (feat/fix/chore/deps/etc. via simple regex), and ticket-linkage rate.
11. **Author concentration** — top contributors per team with per-author table: PRs, mean TTM (merged only), reviews/PR, comments/PR, commits/PR, 0-rev %, pending %. Note bus factor.
12. **Working patterns** — day-of-week distribution of PR creation. Weekend-creation rate.
13. **Repository distribution** — where the PRs land per team.
14. **The long tail — top 10 longest-cycle-time PRs per team** — table with PR number, days to merge, reviews, commits, author, title, URL. **Only merged PRs.** If there are any abandoned (closed-not-merged) PRs in the window, surface them in a small separate sub-table titled "Abandoned PRs in window" with abandon-after-days, author, title, URL. If there are notable still-open PRs, surface them in a third sub-table titled "Still-open PRs (as of data-collection)".
15. **Recommendations** — per-team focus area + cross-team observations. Concrete, actionable, no scolding.
16. **Appendix — raw distribution percentiles** — per team: min, p25, median, mean, p75, p90, p95, max, stdev for time-to-merge in hours and days (merged PRs only). Also: counts of merged / abandoned / still-open PRs per team in the window.

If a section has nothing useful to say for a given run (e.g. all teams used the same convention so classification is trivial), say so in one line rather than omitting the section.

## Hard constraints

- **Cite specific numbers**, always. No vague "Team A is faster." Use "Team A median TTM 25h vs Team B 67h (2.7x)."
- **Median over mean** for any cycle-time / size / count distribution. State means only when contrasting with the median to make a point about tail behaviour.
- **No per-person rankings**. Individual authors are fine to name in context ("vitalinfo's 27 zero-review merges are spec/lint cleanups"), never in a leaderboard.
- **Frame team differences as patterns, not judgments.** "I&I's XL share is double Connect's (27% vs 9%), consistent with an infrastructure team batching larger changes." Not "I&I is slower."
- **Bot-strip before comparing throughput**. Counts including dependabot are misleading. Report both `total` and `human PRs (excl. bots)` if any team has bot activity.
- **Filter to merged PRs for every cycle-time / time-to-merge / TTM-based stat.** Closed-not-merged PRs are NOT long-running open PRs.
- **Avoid 1.00× ratios and obvious tautologies in the headline table.**
- **End with the explicit disclaimer below.**

## Visual style

- Use **matplotlib**. Consistent colours per team across all charts (pick a palette at the top of the run and stick with it). Default font, default sizes; readability over decoration.
- **Log scale on cycle-time axes** where the distribution has a heavy tail (almost always).
- Annotate medians with vertical dashed lines on histograms.
- Save PNGs to `charts/` next to `exec.docx`. Embed into the docx via `doc.add_picture()` at a reasonable inline width (e.g. 6 inches).
- Generate the charts as part of the report-writing process. Don't ship a separate notebook.

## Document formatting (python-docx)

- Use `doc.add_heading()` for section headings (level 1 for the title, level 2 for sections, level 3 for subsections).
- Use `doc.add_table()` for tables. Style: `Light Grid Accent 1` or any clean grid style. Header row bold.
- Use `doc.add_paragraph()` for body text. Plain paragraphs; bold for key inline numbers if helpful.
- Use `doc.add_picture()` for charts, width ~6 inches so it fits a portrait page.
- Page setup: default (Letter or A4 portrait). No special headers/footers required.
- Save as `exec.docx` in the run directory.

## What this report does NOT do (include verbatim near the end)

> ### What this measures (and doesn't)
>
> - **Measures**: PR flow (cycle time, time-to-first-review, size, commits, review iteration) for activity inside the configured GitHub orgs, and calendar load (meeting hours, focus blocks) from Google Calendar freebusy data. Cycle time is computed only for merged PRs.
> - **Does not measure**: code quality, individual impact, work outside GitHub PRs (production incidents, planning, mentorship, customer calls, design docs, pair programming).
> - **Cross-team comparison caveat**: teams ship different kinds of work. Long PR cycle times may reflect riskier, larger-batch changes — not slowness. Treat absolute differences between teams as conversation starters, not rankings.
> - **Most reliable signal is period-over-period for the same team** — same work mix, trend over time.

## When the run includes multiple periods

Add a section after "Headline comparison" called **Period-over-period (per team)** with a delta table. Focus on direction and magnitude of change, not absolute levels (those go in the headline table for the latest period).

## When something is unclear

If the data is ambiguous (e.g. correlation is weak, sample size is small for a team), say so. Better to flag uncertainty than overstate a pattern.
