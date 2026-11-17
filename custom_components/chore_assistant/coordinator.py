"""The Chore Assistant engine.

Owns all chore state, generates Occurrences, schedules due-time wakeups on
HA's event loop, persists to the Store, and emits bus events. This is the
in-process backend that replaces an external server (see ADR 0001).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EVENT_COMPLETED,
    EVENT_DUE,
    EVENT_OVERDUE,
    EVENT_REASSIGNED,
    OVERDUE_CHECK_HOUR,
    SIGNAL_UPDATE,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .models import Chore, Member, Occurrence

_LOGGER = logging.getLogger(__name__)


class ChoreEngine:
    """In-process chore scheduler and system of record."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.members: dict[str, Member] = {}
        self.chores: dict[str, Chore] = {}
        self.occurrences: dict[str, Occurrence] = {}  # keyed by chore_id
        self._timers: dict[str, CALLBACK_TYPE] = {}
        self._unsub_daily: CALLBACK_TYPE | None = None

    # -- lifecycle ---------------------------------------------------------

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if data:
            self.members = {
                m["id"]: Member.from_dict(m) for m in data.get("members", [])
            }
            self.chores = {c["id"]: Chore.from_dict(c) for c in data.get("chores", [])}
            self.occurrences = {
                o["chore_id"]: Occurrence.from_dict(o)
                for o in data.get("occurrences", [])
            }

        # Make sure every enabled chore has an open occurrence, then schedule.
        for chore in self.chores.values():
            if chore.enabled and chore.id not in self.occurrences:
                self._generate_first(chore)
        self._reschedule_all()

        self._unsub_daily = async_track_time_change(
            self.hass, self._async_daily_overdue_check, hour=OVERDUE_CHECK_HOUR,
            minute=0, second=0,
        )

    @callback
    def async_shutdown(self) -> None:
        for unsub in self._timers.values():
            unsub()
        self._timers.clear()
        if self._unsub_daily:
            self._unsub_daily()
            self._unsub_daily = None

    # -- persistence / notification ---------------------------------------

    def _data(self) -> dict:
        return {
            "members": [m.to_dict() for m in self.members.values()],
            "chores": [c.to_dict() for c in self.chores.values()],
            "occurrences": [o.to_dict() for o in self.occurrences.values()],
        }

    @callback
    def _save_and_notify(self) -> None:
        self._store.async_delay_save(self._data, 2)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    # -- scheduling --------------------------------------------------------

    @callback
    def _reschedule_all(self) -> None:
        for chore_id in list(self._timers):
            self._timers.pop(chore_id)()
        for occ in self.occurrences.values():
            self._schedule(occ)

    @callback
    def _schedule(self, occ: Occurrence) -> None:
        if (existing := self._timers.pop(occ.chore_id, None)) is not None:
            existing()
        if occ.due <= dt_util.now():
            return  # already due/overdue; nothing to wait for

        @callback
        def _fire(_now: datetime) -> None:
            self._timers.pop(occ.chore_id, None)
            self._emit(EVENT_DUE, occ)
            async_dispatcher_send(self.hass, SIGNAL_UPDATE)

        self._timers[occ.chore_id] = async_track_point_in_time(
            self.hass, _fire, occ.due
        )

    @callback
    def _async_daily_overdue_check(self, now: datetime) -> None:
        for occ in self.occurrences.values():
            if occ.is_overdue(now):
                self._emit(EVENT_OVERDUE, occ)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    # -- occurrence generation --------------------------------------------

    @callback
    def _generate_first(self, chore: Chore) -> None:
        self.occurrences[chore.id] = Occurrence(
            chore_id=chore.id, due=chore.recurrence.first_due()
        )

    @callback
    def _generate_next(self, chore: Chore, after_due: datetime) -> None:
        self.occurrences[chore.id] = Occurrence(
            chore_id=chore.id, due=chore.recurrence.next_due_after(after_due)
        )
        self._schedule(self.occurrences[chore.id])

    # -- events ------------------------------------------------------------

    @callback
    def _emit(self, event: str, occ: Occurrence, **extra) -> None:
        chore = self.chores.get(occ.chore_id)
        if chore is None:
            return
        member = self.members.get(chore.assignee_id or "")
        self.hass.bus.async_fire(
            event,
            {
                "chore_id": chore.id,
                "chore_name": chore.name,
                "due": occ.due.isoformat(),
                "member_id": chore.assignee_id,
                "member_name": member.name if member else None,
                "person_entity_id": member.person_entity_id if member else None,
                **extra,
            },
        )

    # -- member commands ---------------------------------------------------

    @callback
    def add_member(self, name: str, person_entity_id: str | None = None) -> Member:
        member = Member(name=name, person_entity_id=person_entity_id)
        self.members[member.id] = member
        self._save_and_notify()
        return member

    @callback
    def remove_member(self, member_id: str) -> None:
        self.members.pop(member_id, None)
        for chore in self.chores.values():
            if chore.assignee_id == member_id:
                chore.assignee_id = None
        self._save_and_notify()

    # -- chore commands ----------------------------------------------------

    @callback
    def create_chore(self, chore: Chore) -> Chore:
        self.chores[chore.id] = chore
        if chore.enabled:
            self._generate_first(chore)
            self._schedule(self.occurrences[chore.id])
        self._save_and_notify()
        return chore

    @callback
    def update_chore(self, chore_id: str, changes: dict) -> None:
        chore = self.chores.get(chore_id)
        if chore is None:
            return
        # Only reschedule when the schedule itself changes (or there is no open
        # occurrence yet). A pure metadata edit (name/assignee/description) must
        # not move when the chore is next due.
        reschedule = chore.id not in self.occurrences
        for key, value in changes.items():
            if value is None or not hasattr(chore, key):
                continue
            if key == "recurrence" and value != chore.recurrence:
                reschedule = True
            setattr(chore, key, value)
        if reschedule and chore.enabled:
            self._generate_first(chore)
            self._schedule(self.occurrences[chore.id])
        self._save_and_notify()

    @callback
    def delete_chore(self, chore_id: str) -> None:
        self.chores.pop(chore_id, None)
        self.occurrences.pop(chore_id, None)
        if (unsub := self._timers.pop(chore_id, None)) is not None:
            unsub()
        self._save_and_notify()

    @callback
    def reassign(self, chore_id: str, member_id: str | None) -> None:
        chore = self.chores.get(chore_id)
        if chore is None:
            return
        chore.assignee_id = member_id
        if (occ := self.occurrences.get(chore_id)) is not None:
            self._emit(EVENT_REASSIGNED, occ)
        self._save_and_notify()

    @callback
    def complete(self, chore_id: str, completed_by: str | None = None) -> None:
        chore = self.chores.get(chore_id)
        occ = self.occurrences.get(chore_id)
        if chore is None or occ is None:
            return
        now = dt_util.now()
        chore.last_completed = now
        chore.last_completed_by = completed_by or chore.assignee_id
        member = self.members.get(chore.last_completed_by or "")
        self._emit(
            EVENT_COMPLETED,
            occ,
            completed_by=chore.last_completed_by,
            completed_by_name=member.name if member else None,
            completed_at=now.isoformat(),
        )
        # Next occurrence is schedule-anchored to the original due date.
        self._generate_next(chore, occ.due)
        self._save_and_notify()

    @callback
    def skip(self, chore_id: str) -> None:
        """Advance to the next Occurrence without recording a completion."""
        chore = self.chores.get(chore_id)
        occ = self.occurrences.get(chore_id)
        if chore is None or occ is None:
            return
        self._generate_next(chore, occ.due)
        self._save_and_notify()

    # -- read helpers ------------------------------------------------------

    @callback
    def open_occurrences(self, member_id: str | None = None) -> list[Occurrence]:
        result = []
        for occ in self.occurrences.values():
            chore = self.chores.get(occ.chore_id)
            if chore is None or not chore.enabled:
                continue
            if member_id is not None and chore.assignee_id != member_id:
                continue
            result.append(occ)
        return sorted(result, key=lambda o: o.due)
