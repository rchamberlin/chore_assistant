"""Domain model for Chore Assistant.

These dataclasses are the in-memory source of truth. They know how to
(de)serialize themselves to plain JSON-able dicts for the HA Store, and the
``Recurrence`` type owns the schedule math (next due date computation).

Deliberately free of any Home Assistant entity concerns.
"""

from __future__ import annotations

import calendar as _calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from uuid import uuid4

from homeassistant.util import dt as dt_util

from .const import (
    FREQ_DAILY,
    FREQ_INTERVAL,
    FREQ_MONTHLY,
    FREQ_WEEKLY,
    INTERVAL_UNIT_WEEKS,
)

# Hard ceiling on schedule iteration so a malformed recurrence can never spin.
_MAX_LOOKAHEAD_DAYS = 3660


def new_id() -> str:
    """Return a short unique id."""
    return uuid4().hex[:8]


@dataclass
class Recurrence:
    """When a Chore is due. A Chore is due on a *date* (there is no time of
    day — it just needs doing sometime that day). Next due is always
    schedule-anchored, never computed from completion time."""

    frequency: str = FREQ_DAILY
    anchor_date: date = field(default_factory=lambda: dt_util.now().date())
    # weekly
    weekdays: list[int] = field(default_factory=list)  # 0 = Monday .. 6 = Sunday
    # monthly
    day_of_month: int = 1
    # interval
    interval: int = 1
    interval_unit: str = INTERVAL_UNIT_WEEKS

    # -- schedule math -----------------------------------------------------

    def _matches_or_after(self, d: date) -> date:
        """Smallest scheduled date >= ``d`` (and >= anchor)."""
        d = max(d, self.anchor_date)

        if self.frequency == FREQ_DAILY:
            return d

        if self.frequency == FREQ_WEEKLY:
            wanted = self.weekdays or [self.anchor_date.weekday()]
            for offset in range(7):
                cand = d + timedelta(days=offset)
                if cand.weekday() in wanted:
                    return cand
            return d  # unreachable

        if self.frequency == FREQ_MONTHLY:
            cand = self._clamp_day(d.year, d.month)
            if cand >= d:
                return cand
            year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
            return self._clamp_day(year, month)

        if self.frequency == FREQ_INTERVAL:
            period = self.interval * (7 if self.interval_unit == INTERVAL_UNIT_WEEKS else 1)
            period = max(period, 1)
            diff = (d - self.anchor_date).days
            steps = max(0, -(-diff // period))  # ceil division
            return self.anchor_date + timedelta(days=steps * period)

        return d

    def _clamp_day(self, year: int, month: int) -> date:
        last = _calendar.monthrange(year, month)[1]
        return date(year, month, min(self.day_of_month, last))

    def first_due(self, today: date | None = None) -> date:
        """First occurrence due date, on or after max(anchor, today)."""
        return self._matches_or_after(today or dt_util.now().date())

    def next_due_after(self, due: date) -> date:
        """Next occurrence strictly after the given occurrence's due date."""
        return self._matches_or_after(due + timedelta(days=1))

    def iter_due(self, start: date, end: date):
        """Yield due dates in [start, end] (used by the calendar view)."""
        cur = self._matches_or_after(start)
        guard = 0
        while cur <= end and guard < _MAX_LOOKAHEAD_DAYS:
            yield cur
            cur = self.next_due_after(cur)
            guard += 1

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "frequency": self.frequency,
            "anchor_date": self.anchor_date.isoformat(),
            "weekdays": list(self.weekdays),
            "day_of_month": self.day_of_month,
            "interval": self.interval,
            "interval_unit": self.interval_unit,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Recurrence:
        # ``due_time`` from older stores is intentionally ignored.
        return cls(
            frequency=data.get("frequency", FREQ_DAILY),
            anchor_date=date.fromisoformat(
                data.get("anchor_date", dt_util.now().date().isoformat())
            ),
            weekdays=list(data.get("weekdays", [])),
            day_of_month=data.get("day_of_month", 1),
            interval=data.get("interval", 1),
            interval_unit=data.get("interval_unit", INTERVAL_UNIT_WEEKS),
        )


@dataclass
class Member:
    """A person in the household who can be assigned chores."""

    name: str
    person_entity_id: str | None = None
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "person_entity_id": self.person_entity_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Member:
        return cls(
            id=data["id"],
            name=data["name"],
            person_entity_id=data.get("person_entity_id"),
        )


@dataclass
class Chore:
    """The recurring definition of work. Never itself completed."""

    name: str
    assignee_id: str | None = None
    recurrence: Recurrence = field(default_factory=Recurrence)
    description: str = ""
    enabled: bool = True
    last_completed: datetime | None = None
    last_completed_by: str | None = None
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "assignee_id": self.assignee_id,
            "recurrence": self.recurrence.to_dict(),
            "description": self.description,
            "enabled": self.enabled,
            "last_completed": self.last_completed.isoformat() if self.last_completed else None,
            "last_completed_by": self.last_completed_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Chore:
        lc = data.get("last_completed")
        return cls(
            id=data["id"],
            name=data["name"],
            assignee_id=data.get("assignee_id"),
            recurrence=Recurrence.from_dict(data.get("recurrence", {})),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            last_completed=dt_util.parse_datetime(lc) if lc else None,
            last_completed_by=data.get("last_completed_by"),
        )


@dataclass
class Occurrence:
    """One concrete, due-able instance of a Chore. Exactly one is open per
    Chore at a time. Due on a date — overdue only once that date has passed."""

    chore_id: str
    due: date

    @property
    def uid(self) -> str:
        # One open occurrence per chore, so the chore id is a stable uid.
        return self.chore_id

    def is_overdue(self, today: date | None = None) -> bool:
        return (today or dt_util.now().date()) > self.due

    def to_dict(self) -> dict:
        return {"chore_id": self.chore_id, "due": self.due.isoformat()}

    @classmethod
    def from_dict(cls, data: dict) -> Occurrence:
        # Tolerate older stores that persisted a full datetime for ``due``.
        return cls(chore_id=data["chore_id"], due=date.fromisoformat(data["due"][:10]))
