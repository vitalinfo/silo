"""Serialize a run into metrics.json + INSTRUCTIONS.md.

This replaces the in-tree markdown renderers. silo's job ends at "produce JSON +
a pointer to instructions"; Cowork is invoked separately to read those and
generate the final report (with charts, narrative, structure of its choosing).
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

from .config import RunConfig, Team, TeamsConfig
from .paths import PROJECT_ROOT
from .types import PeriodReport

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def serialize_run(
    run_cfg: RunConfig,
    teams_cfg: TeamsConfig,
    teams: list[Team],
    reports: list[PeriodReport],
    out_dir: Path,
) -> Path:
    """Write metrics.json under out_dir. Returns the path written."""
    by_team: dict[str, list[PeriodReport]] = defaultdict(list)
    for r in reports:
        by_team[r.team].append(r)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "github_orgs": teams_cfg.github_orgs,
            "work_hours": {
                "start": run_cfg.work_hours.start.isoformat(timespec="minutes"),
                "end": run_cfg.work_hours.end.isoformat(timespec="minutes"),
                "workdays": list(run_cfg.work_hours.workdays),
            },
            "periods": [
                {"label": p.label, "from": p.from_.isoformat(), "to": p.to.isoformat()}
                for p in run_cfg.periods
            ],
        },
        "teams": [_serialize_team(t, by_team.get(t.name, [])) for t in teams],
    }

    out_path = out_dir / "metrics.json"
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    log.info("[json] wrote %s (%d bytes)", out_path, out_path.stat().st_size)
    return out_path


def write_instructions(out_dir: Path, reports_requested: list[str]) -> Path:
    """Write a per-run INSTRUCTIONS.md pointing Cowork at the right prompt template."""
    prompts_dir = (PROJECT_ROOT / "prompts").resolve()
    json_path = (out_dir / "metrics.json").resolve()
    sections = []
    for kind in reports_requested:
        prompt_path = prompts_dir / f"{kind}.md"
        sections.append(
            f"### {kind} report\n"
            f"- Read the instructions: `{prompt_path}`\n"
            f"- Use the data file: `{json_path}`\n"
            f"- Write the rendered report into this directory as `{kind}.docx`."
        )
    body = dedent(f"""\
        # silo run — report generation instructions

        This file is the entrypoint for Cowork. Open this project in Cowork and ask it to
        follow the steps below. Cowork reads the per-report prompts in `prompts/`, the
        metrics in `metrics.json`, and writes the final Word-format reports here.

        Generated at: {datetime.now(timezone.utc).isoformat()}

        ## Reports to produce

        {chr(10).join(sections)}

        ## Notes

        - Reports are produced as **`.docx`** (Word) — easier to share with execs than markdown.
          Use `python-docx` (installed via the `[report]` extra) for document construction.
        - Charts are generated with matplotlib and embedded inline via `doc.add_picture()`
          (BytesIO buffer or temp file is fine; no separate charts directory needed since
          they live inside the docx).
        - Do not modify `metrics.json` — it is the canonical input.
        - **PR state semantics**: each PR has `merged_at` and `closed_at`. Cycle-time
          and "long-running" analyses must filter to `merged_at is not None`. Closed-not-
          merged PRs are abandoned and should be reported separately, never as "still open".
        """)
    out_path = out_dir / "INSTRUCTIONS.md"
    out_path.write_text(body)
    return out_path


# --- internal -------------------------------------------------------------

def _serialize_team(team: Team, reports: list[PeriodReport]) -> dict:
    return {
        "name": team.name,
        "lead": team.lead,
        "members": [
            {"github": m.github, "google": m.google, "tz": m.tz} for m in team.members
        ],
        "periods": [_serialize_period(r) for r in reports],
    }


def _serialize_period(r: PeriodReport) -> dict:
    out = {
        "label": r.period_label,
        "from": r.period_from.isoformat(),
        "to": r.period_to.isoformat(),
        "team_metrics": r.team_metrics.model_dump(),
        "person_metrics": [pm.model_dump() for pm in r.person_metrics],
    }
    if r.raw is not None:
        out["raw"] = {
            "prs": [pr.model_dump(mode="json") for pr in r.raw.prs],
            "reviews_given": [rv.model_dump(mode="json") for rv in r.raw.reviews_given],
            "comments_left": [c.model_dump(mode="json") for c in r.raw.comments_left],
            "busy_blocks_by_member": {
                email: [b.model_dump(mode="json") for b in blocks]
                for email, blocks in r.raw.busy_blocks_by_member.items()
            },
            "all_day_blocks_by_member": {
                email: [b.model_dump(mode="json") for b in blocks]
                for email, blocks in r.raw.all_day_blocks_by_member.items()
            },
        }
    return out
