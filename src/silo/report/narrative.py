"""Claude API wrapper for narrative generation.

Two prompts: one for team-lead reports (per-person aware), one for exec reports
(team-level only, no per-person callouts). Prompts emphasize "patterns worth
discussing" framing — no rankings, no scores.
"""
from __future__ import annotations

from typing import Literal

from ..types import PeriodReport


def generate_team_lead_narrative(reports: list[PeriodReport], api_key: str) -> str:
    raise NotImplementedError


def generate_exec_narrative(reports: list[PeriodReport], api_key: str) -> str:
    raise NotImplementedError


NarrativeKind = Literal["team_lead", "exec"]
