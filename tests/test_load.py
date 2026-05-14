"""Load-metric tests. Uses America/New_York (UTC-5 in January, no DST) for predictable math."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from silo.config import WorkHours
from silo.metrics.load import (
    after_hours_busy_per_week,
    focus_block_hours_per_week,
    fragmentation_score,
    is_all_day_in_tz,
    meeting_hours_per_week,
    partition_all_day,
)
from silo.types import BusyBlock


WH = WorkHours.model_validate({
    "start": "09:00",
    "end": "17:00",
    "workdays": ["mon", "tue", "wed", "thu", "fri"],
})
TZ = ZoneInfo("America/New_York")

# 5-workday window: Mon 2026-01-05 .. Fri 2026-01-09.
FRM = date(2026, 1, 5)
TO = date(2026, 1, 9)
# 5 days inclusive = 5/7 weeks
PERIOD_WEEKS = 5 / 7


def _block(start_utc: datetime, end_utc: datetime) -> BusyBlock:
    return BusyBlock(google_email="x@example.com", start=start_utc, end=end_utc)


def test_meeting_hours_per_week_intersects_work_window():
    # 1 hour meeting Mon 14:00-15:00 NY = 19:00-20:00 UTC
    blocks = [_block(
        datetime(2026, 1, 5, 19, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 5, 20, 0, tzinfo=timezone.utc),
    )]
    out = meeting_hours_per_week(blocks, WH, TZ, FRM, TO)
    assert out == pytest.approx(1.0 / PERIOD_WEEKS)


def test_meeting_hours_per_week_excludes_block_outside_work():
    # Block Mon 06:00-07:00 NY = 11:00-12:00 UTC, before work
    blocks = [_block(
        datetime(2026, 1, 5, 11, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc),
    )]
    assert meeting_hours_per_week(blocks, WH, TZ, FRM, TO) == 0.0


def test_focus_blocks_empty_calendar_is_full_workdays():
    # 5 workdays * 8 hours each = 40 focus hours
    assert focus_block_hours_per_week([], WH, TZ, FRM, TO) == pytest.approx(40 / PERIOD_WEEKS)


def test_focus_blocks_split_by_meeting():
    # 1-hour meeting Mon 12:00-13:00 NY (17:00-18:00 UTC) splits Mon (9-17 NY = 8h) into
    # 3h pre (9-12 NY) + 4h post (13-17 NY) = 7h focus. Tue-Fri = 8h * 4 = 32h. Total = 39h.
    blocks = [_block(
        datetime(2026, 1, 5, 17, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 5, 18, 0, tzinfo=timezone.utc),
    )]
    assert focus_block_hours_per_week(blocks, WH, TZ, FRM, TO) == pytest.approx(39 / PERIOD_WEEKS)


def test_focus_blocks_drop_short_gaps():
    # Two meetings on Mon at 11-12 and 13-14 NY split day into [9-11=2h] [12-13=1h] [14-17=3h]
    # 2h gap: just at threshold? Threshold is >= 2.0, so 2h counts.
    # The 1h middle gap is dropped.
    # Mon focus = 2 + 3 = 5h. Tue-Fri = 32h. Total = 37h.
    blocks = [
        _block(datetime(2026, 1, 5, 16, 0, tzinfo=timezone.utc),
               datetime(2026, 1, 5, 17, 0, tzinfo=timezone.utc)),  # 11-12 NY
        _block(datetime(2026, 1, 5, 18, 0, tzinfo=timezone.utc),
               datetime(2026, 1, 5, 19, 0, tzinfo=timezone.utc)),  # 13-14 NY
    ]
    assert focus_block_hours_per_week(blocks, WH, TZ, FRM, TO) == pytest.approx(37 / PERIOD_WEEKS)


def test_fragmentation_score_blocks_per_work_hour():
    # 5 workdays * 8h = 40 work-hours. 2 distinct meetings on Mon.
    blocks = [
        _block(datetime(2026, 1, 5, 16, 0, tzinfo=timezone.utc),
               datetime(2026, 1, 5, 17, 0, tzinfo=timezone.utc)),
        _block(datetime(2026, 1, 5, 18, 0, tzinfo=timezone.utc),
               datetime(2026, 1, 5, 19, 0, tzinfo=timezone.utc)),
    ]
    assert fragmentation_score(blocks, WH, TZ, FRM, TO) == pytest.approx(2 / 40)


def test_after_hours_block_outside_work_window():
    # Mon 18:00-19:00 NY = 23:00-24:00 UTC (after 17:00 end)
    blocks = [_block(
        datetime(2026, 1, 5, 23, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 6, 0, 0, tzinfo=timezone.utc),
    )]
    assert after_hours_busy_per_week(blocks, WH, TZ, FRM, TO) == pytest.approx(1.0 / PERIOD_WEEKS)


def test_after_hours_weekend_excluded_period_but_block_outside_counts_when_in_range():
    # Mon 06:00 NY (11:00 UTC) - 09:00 NY (14:00 UTC). 3h before work.
    blocks = [_block(
        datetime(2026, 1, 5, 11, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 5, 14, 0, tzinfo=timezone.utc),
    )]
    assert after_hours_busy_per_week(blocks, WH, TZ, FRM, TO) == pytest.approx(3.0 / PERIOD_WEEKS)


def test_after_hours_split_block_counts_only_outside_portion():
    # Mon 08:00 NY - 10:00 NY = 13:00-15:00 UTC. 1h before work + 1h inside.
    blocks = [_block(
        datetime(2026, 1, 5, 13, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 5, 15, 0, tzinfo=timezone.utc),
    )]
    assert after_hours_busy_per_week(blocks, WH, TZ, FRM, TO) == pytest.approx(1.0 / PERIOD_WEEKS)


# --- all-day detection ----------------------------------------------------

def test_is_all_day_single_day_pto():
    # PTO on Mon Jan 5 NY = 2026-01-05 00:00 NY (05:00 UTC) -> 2026-01-06 00:00 NY (05:00 UTC)
    b = _block(
        datetime(2026, 1, 5, 5, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 6, 5, 0, tzinfo=timezone.utc),
    )
    assert is_all_day_in_tz(b, TZ) is True


def test_is_all_day_multi_day_vacation():
    # Vacation Mon-Fri NY = 5 days
    b = _block(
        datetime(2026, 1, 5, 5, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 10, 5, 0, tzinfo=timezone.utc),
    )
    assert is_all_day_in_tz(b, TZ) is True


def test_is_all_day_regular_meeting_is_not():
    # 10:00-11:00 NY = 15:00-16:00 UTC
    b = _block(
        datetime(2026, 1, 5, 15, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 5, 16, 0, tzinfo=timezone.utc),
    )
    assert is_all_day_in_tz(b, TZ) is False


def test_partition_separates_pto_from_meetings():
    meeting = _block(
        datetime(2026, 1, 5, 15, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 5, 16, 0, tzinfo=timezone.utc),
    )
    pto = _block(
        datetime(2026, 1, 5, 5, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 6, 5, 0, tzinfo=timezone.utc),
    )
    regular, all_day = partition_all_day([meeting, pto, meeting], TZ)
    assert regular == [meeting, meeting]
    assert all_day == [pto]
