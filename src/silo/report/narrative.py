"""Claude narrative generation for team-lead and exec reports.

Prompts emphasize "patterns worth discussing" framing — no rankings, no scores,
no per-person callouts in exec narrative. The metric data is passed as JSON
so the model has structured numbers to cite.
"""
from __future__ import annotations

import json
import logging
from typing import Iterable

import anthropic

from ..types import PeriodReport

log = logging.getLogger(__name__)

MODEL = "claude-opus-4-7"
MAX_TOKENS = 1500

SYSTEM_TEAM_LEAD = """\
You are an assistant helping a team lead interpret their team's engineering activity \
over one or more time periods. You are given structured metrics. Your job is to surface \
3-5 patterns worth discussing in a 1:1 or retro — written as short paragraphs.

Hard rules:
- Cite specific numbers from the data; do not invent values.
- Frame findings as questions or hypotheses, never as judgments or scores.
- Do not rank people. If you mention a person by GitHub handle, do so as context \
("Alice's review latency rose 40%, worth asking if her load shifted") not as scoring.
- If period-over-period data is present, the most useful patterns are usually changes, not levels.
- When in doubt, ask a question rather than make a claim.
- Markdown is fine but keep it light — short paragraphs, no headers, no tables.
"""

SYSTEM_EXEC = """\
You are an assistant helping a CTO or VP interpret team-level engineering activity \
across multiple teams and time periods. You are given structured team-level metrics. \
Your job is to surface 3-5 patterns worth discussing — written as short paragraphs.

Hard rules:
- Do not mention individuals by name or handle. No per-person callouts.
- Cite specific numbers from the data; do not invent values.
- Frame findings as questions or hypotheses, never as scores or rankings.
- When comparing teams, focus on changes over time, not absolute leadership.
- A team with longer cycle times may be doing different work — note this when relevant \
rather than implying performance.
- Markdown is fine but keep it light — short paragraphs, no headers, no tables.
"""


def generate_team_lead_narrative(reports: Iterable[PeriodReport], api_key: str) -> str:
    """Generate narrative for one team across one or more periods."""
    payload = [_report_dict(r, include_person=True) for r in reports]
    return _call(api_key, SYSTEM_TEAM_LEAD, _user_prompt_team_lead(payload))


def generate_exec_narrative(reports: Iterable[PeriodReport], api_key: str) -> str:
    """Generate narrative across all teams and periods. Per-person data stripped."""
    payload = [_report_dict(r, include_person=False) for r in reports]
    return _call(api_key, SYSTEM_EXEC, _user_prompt_exec(payload))


# --- internals -----------------------------------------------------------

def _report_dict(r: PeriodReport, include_person: bool) -> dict:
    d = {
        "period": r.period_label,
        "team": r.team,
        "team_metrics": r.team_metrics.model_dump(),
    }
    if include_person:
        d["person_metrics"] = [pm.model_dump() for pm in r.person_metrics]
    return d


def _user_prompt_team_lead(payload: list[dict]) -> str:
    return (
        "Team metrics across one or more periods are below. Identify 3-5 patterns "
        "worth discussing with the team. Cite specific numbers.\n\n"
        f"```json\n{json.dumps(payload, indent=2, default=str)}\n```"
    )


def _user_prompt_exec(payload: list[dict]) -> str:
    return (
        "Team-level metrics across multiple teams and periods are below (no per-person "
        "data is included). Identify 3-5 patterns worth discussing at the leadership "
        "level. Cite specific numbers.\n\n"
        f"```json\n{json.dumps(payload, indent=2, default=str)}\n```"
    )


def _call(api_key: str, system: str, user: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = [block.text for block in msg.content if block.type == "text"]
    return "\n\n".join(parts).strip()
