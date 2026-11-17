"""Tests for the recurrence/schedule math in models.Recurrence.

Chores are due on a *date* (no time of day). All tests pass explicit dates so
they are fully deterministic and never depend on the real clock.
(2026-01-01 is a Thursday.)
"""

from __future__ import annotations

from datetime import date

from ca.models import Recurrence


# --- daily ----------------------------------------------------------------


def test_daily_first_due_is_today_when_after_anchor():
    r = Recurrence(frequency="daily", anchor_date=date(2026, 1, 1))
    assert r.first_due(date(2026, 1, 5)) == date(2026, 1, 5)


def test_daily_next_due_is_tomorrow():
    r = Recurrence(frequency="daily", anchor_date=date(2026, 1, 1))
    assert r.next_due_after(date(2026, 1, 5)) == date(2026, 1, 6)


def test_first_due_not_before_future_anchor():
    r = Recurrence(frequency="daily", anchor_date=date(2026, 12, 25))
    assert r.first_due(date(2026, 6, 1)) == date(2026, 12, 25)


# --- weekly ---------------------------------------------------------------


def test_weekly_single_weekday():
    # Tuesdays (weekday 1). First Tuesday on/after Thu 2026-01-01 is 2026-01-06.
    r = Recurrence(frequency="weekly", weekdays=[1], anchor_date=date(2026, 1, 1))
    assert r.first_due(date(2026, 1, 1)) == date(2026, 1, 6)
    assert r.next_due_after(date(2026, 1, 6)) == date(2026, 1, 13)


def test_weekly_multiple_weekdays_interleave():
    # Tuesday (1) and Saturday (5). Anchor Thu 2026-01-01, so the first match
    # scanning forward is Sat 2026-01-03, then it alternates Tue/Sat.
    r = Recurrence(frequency="weekly", weekdays=[1, 5], anchor_date=date(2026, 1, 1))
    assert r.first_due(date(2026, 1, 1)) == date(2026, 1, 3)  # Sat
    assert r.next_due_after(date(2026, 1, 3)) == date(2026, 1, 6)  # Tue
    assert r.next_due_after(date(2026, 1, 6)) == date(2026, 1, 10)  # Sat
    assert r.next_due_after(date(2026, 1, 10)) == date(2026, 1, 13)  # Tue


def test_weekly_empty_weekdays_falls_back_to_anchor_weekday():
    # Anchor is a Thursday; with no weekdays set it should recur on Thursdays.
    r = Recurrence(frequency="weekly", weekdays=[], anchor_date=date(2026, 1, 1))
    nxt = r.next_due_after(date(2026, 1, 1))
    assert nxt == date(2026, 1, 8)
    assert nxt.weekday() == 3


# --- monthly --------------------------------------------------------------


def test_monthly_rolls_to_next_month_when_day_passed():
    r = Recurrence(frequency="monthly", day_of_month=15, anchor_date=date(2026, 1, 1))
    assert r.first_due(date(2026, 1, 20)) == date(2026, 2, 15)


def test_monthly_clamps_to_short_month():
    # Day 31 in February 2026 (28 days) clamps to the 28th.
    r = Recurrence(frequency="monthly", day_of_month=31, anchor_date=date(2026, 2, 1))
    assert r.first_due(date(2026, 2, 1)) == date(2026, 2, 28)
    # ...and the following month restores the 31st.
    assert r.next_due_after(date(2026, 2, 28)) == date(2026, 3, 31)


def test_monthly_year_rollover():
    r = Recurrence(frequency="monthly", day_of_month=15, anchor_date=date(2026, 1, 1))
    assert r.next_due_after(date(2026, 12, 20)) == date(2027, 1, 15)


# --- interval -------------------------------------------------------------


def test_interval_days_phase_from_anchor():
    # Every 3 days from 2026-01-01 -> 1, 4, 7, 10 ...
    r = Recurrence(
        frequency="interval", interval=3, interval_unit="days",
        anchor_date=date(2026, 1, 1),
    )
    assert r.first_due(date(2026, 1, 2)) == date(2026, 1, 4)
    assert r.next_due_after(date(2026, 1, 4)) == date(2026, 1, 7)


def test_interval_weeks():
    # Every 2 weeks from Tue 2026-01-06 -> 6 Jan, 20 Jan, 3 Feb ...
    r = Recurrence(
        frequency="interval", interval=2, interval_unit="weeks",
        anchor_date=date(2026, 1, 6),
    )
    assert r.next_due_after(date(2026, 1, 6)) == date(2026, 1, 20)
    assert r.next_due_after(date(2026, 1, 20)) == date(2026, 2, 3)


def test_interval_due_exactly_on_anchor_phase():
    r = Recurrence(
        frequency="interval", interval=2, interval_unit="weeks",
        anchor_date=date(2026, 1, 6),
    )
    # An as-of date that is on a scheduled day returns that day for first_due.
    assert r.first_due(date(2026, 1, 6)) == date(2026, 1, 6)


# --- the "phased alternation" scenario (no rotation engine) ---------------


def test_two_phased_chores_alternate_biweekly():
    """A biweekly chore shared by two people, each doing it every 4 weeks, is
    modelled as two every-4-week chores whose anchors are 2 weeks apart. The
    merged schedule must land every 2 weeks, strictly alternating owners."""
    kid1 = Recurrence(
        frequency="interval", interval=4, interval_unit="weeks",
        anchor_date=date(2026, 1, 6),
    )
    kid2 = Recurrence(
        frequency="interval", interval=4, interval_unit="weeks",
        anchor_date=date(2026, 1, 20),
    )
    start, end = date(2026, 1, 1), date(2026, 4, 1)
    merged = sorted(
        [(due, "kid1") for due in kid1.iter_due(start, end)]
        + [(due, "kid2") for due in kid2.iter_due(start, end)]
    )
    dates = [d for d, _ in merged]
    owners = [o for _, o in merged]

    # Starts correctly and strictly alternates.
    assert dates[0] == date(2026, 1, 6)
    assert owners[:4] == ["kid1", "kid2", "kid1", "kid2"]
    # Exactly 14 days between every consecutive cleaning.
    gaps = {(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)}
    assert gaps == {14}


# --- iter_due -------------------------------------------------------------


def test_iter_due_bounds_are_inclusive_and_ordered():
    r = Recurrence(frequency="daily", anchor_date=date(2026, 1, 1))
    due = list(r.iter_due(date(2026, 1, 1), date(2026, 1, 5)))
    assert due == [
        date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3),
        date(2026, 1, 4), date(2026, 1, 5),
    ]


def test_iter_due_starts_at_anchor_when_window_opens_earlier():
    # Window opens 2026-01-01 but the chore does not start until the 3rd.
    r = Recurrence(frequency="daily", anchor_date=date(2026, 1, 3))
    due = list(r.iter_due(date(2026, 1, 1), date(2026, 1, 5)))
    assert due == [date(2026, 1, 3), date(2026, 1, 4), date(2026, 1, 5)]
