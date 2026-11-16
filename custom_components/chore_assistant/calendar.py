"""Calendar platform: a dedicated Chores calendar of upcoming Occurrences.

Read-only projection of the schedule. We never write into any other
calendar (see DESIGN.md Q13).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ChoreConfigEntry
from .const import SIGNAL_UPDATE

# How long a chore "event" visually occupies on the calendar.
_EVENT_DURATION = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChoreConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([ChoreCalendar(entry)])


class ChoreCalendar(CalendarEntity):
    """All chore occurrences on one calendar."""

    _attr_has_entity_name = True
    _attr_name = "Chores"

    def __init__(self, entry: ChoreConfigEntry) -> None:
        self._entry = entry
        self._engine = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_calendar"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE, self.async_write_ha_state
            )
        )

    def _event_for(self, chore_id: str, due: datetime) -> CalendarEvent:
        chore = self._engine.chores[chore_id]
        member = self._engine.members.get(chore.assignee_id or "")
        suffix = f" ({member.name})" if member else ""
        return CalendarEvent(
            start=due,
            end=due + _EVENT_DURATION,
            summary=f"{chore.name}{suffix}",
            description=chore.description or None,
            uid=f"{chore_id}:{due.isoformat()}",
        )

    @property
    def event(self) -> CalendarEvent | None:
        """The soonest open occurrence."""
        occ = next(iter(self._engine.open_occurrences()), None)
        return self._event_for(occ.chore_id, occ.due) if occ else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        for chore in self._engine.chores.values():
            if not chore.enabled:
                continue
            for due in chore.recurrence.iter_due(start_date, end_date):
                events.append(self._event_for(chore.id, due))
        return sorted(events, key=lambda e: e.start)
