"""Calendar-derived load metrics: meetings, focus blocks, fragmentation, after-hours.

All metrics are normalized to per-week rates so periods of different lengths can be
compared. Busy blocks come in as tz-aware datetimes (UTC from freebusy). Work
windows are interpreted in `WorkHours.tz` and converted to UTC for intersection.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterator

from ..config import WorkHours
from ..types import BusyBlock

FOCUS_BLOCK_MIN_HOURS = 2.0
_SECONDS_PER_HOUR = 3600.0


def meeting_hours_per_week(blocks: list[BusyBlock], wh: WorkHours, frm: date, to: date) -> float:
    """Total busy hours that intersect a work-window, per week."""
    work_windows = list(_workday_windows(frm, to, wh))
    total_seconds = 0.0
    for b in blocks:
        for ws, we in work_windows:
            inter = _intersect(b.start, b.end, ws, we)
            if inter is not None:
                total_seconds += (inter[1] - inter[0]).total_seconds()
    return (total_seconds / _SECONDS_PER_HOUR) / _period_weeks(frm, to)


def focus_block_hours_per_week(
    blocks: list[BusyBlock], wh: WorkHours, frm: date, to: date
) -> float:
    """Per-workday: find gaps between busy blocks within the work window. Sum gaps
    >= FOCUS_BLOCK_MIN_HOURS. Return total focus hours per week."""
    total_seconds = 0.0
    for ws, we in _workday_windows(frm, to, wh):
        day_busy = sorted(
            [
                inter
                for b in blocks
                if (inter := _intersect(b.start, b.end, ws, we)) is not None
            ],
            key=lambda iv: iv[0],
        )
        merged = _merge_intervals(day_busy)
        # build gaps: [ws -> first.start], [busy_i.end -> busy_{i+1}.start], [last.end -> we]
        cursor = ws
        for bs, be in merged:
            gap_seconds = (bs - cursor).total_seconds()
            if gap_seconds >= FOCUS_BLOCK_MIN_HOURS * _SECONDS_PER_HOUR:
                total_seconds += gap_seconds
            cursor = be
        tail = (we - cursor).total_seconds()
        if tail >= FOCUS_BLOCK_MIN_HOURS * _SECONDS_PER_HOUR:
            total_seconds += tail
    return (total_seconds / _SECONDS_PER_HOUR) / _period_weeks(frm, to)


def fragmentation_score(blocks: list[BusyBlock], wh: WorkHours, frm: date, to: date) -> float:
    """Average busy-blocks-per-work-hour across workdays. Higher = more fragmented.

    Captures the intuition that 4 one-hour meetings split across a day is worse
    than one 4-hour block — same total time, different shape."""
    work_windows = list(_workday_windows(frm, to, wh))
    if not work_windows:
        return 0.0
    total_blocks = 0
    total_work_hours = 0.0
    for ws, we in work_windows:
        day_busy = [
            inter
            for b in blocks
            if (inter := _intersect(b.start, b.end, ws, we)) is not None
        ]
        merged = _merge_intervals(sorted(day_busy, key=lambda iv: iv[0]))
        total_blocks += len(merged)
        total_work_hours += (we - ws).total_seconds() / _SECONDS_PER_HOUR
    if total_work_hours == 0:
        return 0.0
    return total_blocks / total_work_hours


def after_hours_busy_per_week(
    blocks: list[BusyBlock], wh: WorkHours, frm: date, to: date
) -> float:
    """Busy hours OUTSIDE work windows (evenings, weekends), per week."""
    period_start = datetime.combine(frm, datetime.min.time(), tzinfo=wh.zoneinfo).astimezone(timezone.utc)
    period_end = datetime.combine(to, datetime.max.time(), tzinfo=wh.zoneinfo).astimezone(timezone.utc)

    work_windows = list(_workday_windows(frm, to, wh))
    after_seconds = 0.0
    for b in blocks:
        # Clip block to the period boundaries.
        bs = max(b.start, period_start)
        be = min(b.end, period_end)
        if bs >= be:
            continue
        block_seconds = (be - bs).total_seconds()
        # Subtract the parts that fall inside any work window.
        inside_seconds = 0.0
        for ws, we in work_windows:
            inter = _intersect(bs, be, ws, we)
            if inter is not None:
                inside_seconds += (inter[1] - inter[0]).total_seconds()
        after_seconds += max(0.0, block_seconds - inside_seconds)
    return (after_seconds / _SECONDS_PER_HOUR) / _period_weeks(frm, to)


# --- helpers --------------------------------------------------------------

def _work_window_for_day(d: date, wh: WorkHours) -> tuple[datetime, datetime]:
    tz = wh.zoneinfo
    start_local = datetime.combine(d, wh.start, tzinfo=tz)
    end_local = datetime.combine(d, wh.end, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _workday_windows(frm: date, to: date, wh: WorkHours) -> Iterator[tuple[datetime, datetime]]:
    cur = frm
    workdays = wh.workday_indices
    while cur <= to:
        if cur.weekday() in workdays:
            yield _work_window_for_day(cur, wh)
        cur += timedelta(days=1)


def _intersect(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> tuple[datetime, datetime] | None:
    s = max(a_start, b_start)
    e = min(a_end, b_end)
    if s >= e:
        return None
    return s, e


def _merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Merge overlapping/adjacent intervals. Input must be sorted by start."""
    if not intervals:
        return []
    out = [intervals[0]]
    for s, e in intervals[1:]:
        last_s, last_e = out[-1]
        if s <= last_e:
            out[-1] = (last_s, max(last_e, e))
        else:
            out.append((s, e))
    return out


def _period_weeks(frm: date, to: date) -> float:
    days = (to - frm).days + 1
    return days / 7
