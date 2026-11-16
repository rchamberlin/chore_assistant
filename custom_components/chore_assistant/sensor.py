"""Sensor platform: one per-Member sensor summarising their chore load."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ChoreConfigEntry
from .const import SIGNAL_UPDATE
from .coordinator import ChoreEngine


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChoreConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    engine = entry.runtime_data
    known: set[str] = set()

    @callback
    def _sync() -> None:
        new: list[MemberChoreSensor] = []
        for member_id in engine.members:
            if member_id not in known:
                known.add(member_id)
                new.append(MemberChoreSensor(entry, engine, member_id))
        if new:
            async_add_entities(new)

    _sync()
    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_UPDATE, _sync))


class MemberChoreSensor(SensorEntity):
    """Number of overdue chores for a member, with detail attributes."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:broom"
    _attr_native_unit_of_measurement = "chores"

    def __init__(
        self, entry: ChoreConfigEntry, engine: ChoreEngine, member_id: str
    ) -> None:
        self._engine = engine
        self._member_id = member_id
        member = engine.members[member_id]
        self._attr_name = f"{member.name} overdue chores"
        self._attr_unique_id = f"{entry.entry_id}_sensor_{member_id}"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE, self.async_write_ha_state
            )
        )

    @property
    def native_value(self) -> int:
        now = dt_util.now()
        return sum(
            occ.is_overdue(now)
            for occ in self._engine.open_occurrences(self._member_id)
        )

    @property
    def extra_state_attributes(self) -> dict:
        now = dt_util.now()
        today = now.date()
        occs = self._engine.open_occurrences(self._member_id)
        nxt = occs[0] if occs else None
        return {
            "open_total": len(occs),
            "due_today": sum(o.due.date() == today for o in occs),
            "next_due": nxt.due.isoformat() if nxt else None,
            "next_chore": self._engine.chores[nxt.chore_id].name if nxt else None,
        }
