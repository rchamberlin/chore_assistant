"""Todo list platform: a unified Chores list plus one list per Member."""

from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChoreConfigEntry
from .const import DOMAIN, SIGNAL_UPDATE
from .coordinator import ChoreEngine


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChoreConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    engine = entry.runtime_data
    known_members: set[str] = set()

    @callback
    def _sync_entities() -> None:
        new: list[TodoListEntity] = []
        for member_id in engine.members:
            if member_id not in known_members:
                known_members.add(member_id)
                new.append(MemberChoreList(entry, engine, member_id))
        if new:
            async_add_entities(new)

    async_add_entities([UnifiedChoreList(entry, engine)])
    _sync_entities()
    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_UPDATE, _sync_entities))


class _BaseChoreList(TodoListEntity):
    """Shared behaviour for the chore todo lists."""

    _attr_has_entity_name = True
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM
    _member_id: str | None = None

    def __init__(self, entry: ChoreConfigEntry, engine: ChoreEngine) -> None:
        self._entry = entry
        self._engine = engine

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE, self.async_write_ha_state
            )
        )

    @property
    def todo_items(self) -> list[TodoItem]:
        items: list[TodoItem] = []
        for occ in self._engine.open_occurrences(self._member_id):
            chore = self._engine.chores[occ.chore_id]
            items.append(
                TodoItem(
                    uid=occ.uid,
                    summary=chore.name,
                    status=TodoItemStatus.NEEDS_ACTION,
                    due=occ.due,
                    description=chore.description or None,
                )
            )
        return items

    async def async_update_todo_item(self, item: TodoItem) -> None:
        # The only update we honour is ticking an item complete.
        if item.status == TodoItemStatus.COMPLETED and item.uid:
            self._engine.complete(item.uid)


class UnifiedChoreList(_BaseChoreList):
    """All open chores across the household."""

    def __init__(self, entry: ChoreConfigEntry, engine: ChoreEngine) -> None:
        super().__init__(entry, engine)
        self._attr_name = "Chores"
        self._attr_unique_id = f"{entry.entry_id}_todo_all"


class MemberChoreList(_BaseChoreList):
    """One member's open chores."""

    def __init__(
        self, entry: ChoreConfigEntry, engine: ChoreEngine, member_id: str
    ) -> None:
        super().__init__(entry, engine)
        self._member_id = member_id
        member = engine.members[member_id]
        self._attr_name = f"{member.name} chores"
        self._attr_unique_id = f"{entry.entry_id}_todo_member_{member_id}"
