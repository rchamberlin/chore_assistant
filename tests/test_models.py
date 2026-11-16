"""Tests for serialization round-trips and Occurrence behaviour."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from ca.models import Chore, Member, Occurrence, Recurrence, new_id

UTC = timezone.utc


def test_new_id_is_unique_and_short():
    ids = {new_id() for _ in range(1000)}
    assert len(ids) == 1000
    assert all(len(i) == 8 for i in ids)


def test_recurrence_round_trip():
    r = Recurrence(
        frequency="interval",
        due_time=time(7, 30),
        anchor_date=date(2026, 3, 9),
        weekdays=[1, 5],
        day_of_month=12,
        interval=4,
        interval_unit="weeks",
    )
    assert Recurrence.from_dict(r.to_dict()).to_dict() == r.to_dict()


def test_member_round_trip_with_and_without_person():
    linked = Member(name="Kid One", person_entity_id="person.kid_one")
    unlinked = Member(name="Guest")
    for m in (linked, unlinked):
        restored = Member.from_dict(m.to_dict())
        assert restored.id == m.id
        assert restored.name == m.name
        assert restored.person_entity_id == m.person_entity_id


def test_chore_round_trip_preserves_everything():
    chore = Chore(
        name="Clean bathroom",
        assignee_id="abc123",
        recurrence=Recurrence(frequency="weekly", weekdays=[1]),
        description="wipe counters\nsweep floor",
        enabled=True,
        last_completed=datetime(2026, 1, 6, 9, 0, tzinfo=UTC),
        last_completed_by="abc123",
    )
    restored = Chore.from_dict(chore.to_dict())
    assert restored.to_dict() == chore.to_dict()
    assert restored.last_completed == chore.last_completed
    assert restored.description == "wipe counters\nsweep floor"


def test_chore_round_trip_without_completion():
    chore = Chore(name="Trash", assignee_id=None)
    restored = Chore.from_dict(chore.to_dict())
    assert restored.last_completed is None
    assert restored.last_completed_by is None
    assert restored.assignee_id is None


def test_occurrence_round_trip_and_uid():
    occ = Occurrence(chore_id="xyz789", due=datetime(2026, 2, 1, 9, 0, tzinfo=UTC))
    restored = Occurrence.from_dict(occ.to_dict())
    assert restored.chore_id == occ.chore_id
    assert restored.due == occ.due
    # One open occurrence per chore, so uid is the chore id.
    assert restored.uid == "xyz789"


def test_occurrence_is_overdue():
    now = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
    past = Occurrence(chore_id="c", due=datetime(2026, 2, 1, 9, 0, tzinfo=UTC))
    future = Occurrence(chore_id="c", due=datetime(2026, 2, 1, 18, 0, tzinfo=UTC))
    assert past.is_overdue(now) is True
    assert future.is_overdue(now) is False
