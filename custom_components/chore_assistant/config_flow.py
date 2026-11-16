"""Config and options flow for Chore Assistant.

The integration is a single household, so there is exactly one config entry
and it needs no configuration. All ongoing management (members and chores)
happens in the options flow, which drives the engine directly.
"""

from __future__ import annotations

from datetime import date, time
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    FREQ_INTERVAL,
    FREQ_MONTHLY,
    FREQ_WEEKLY,
    FREQUENCIES,
    INTERVAL_UNITS,
)
from .models import Chore, Recurrence

_WEEKDAYS = [
    ("0", "Monday"),
    ("1", "Tuesday"),
    ("2", "Wednesday"),
    ("3", "Thursday"),
    ("4", "Friday"),
    ("5", "Saturday"),
    ("6", "Sunday"),
]


class ChoreAssistantConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single household entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Chore Assistant", data={})

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ChoreAssistantOptionsFlow()


class ChoreAssistantOptionsFlow(OptionsFlow):
    """Add/remove members and chores."""

    @property
    def _engine(self):
        return self.config_entry.runtime_data

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "add_member",
                "remove_member",
                "add_chore",
                "remove_chore",
            ],
        )

    # -- members -----------------------------------------------------------

    async def async_step_add_member(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._engine.add_member(
                user_input["name"], user_input.get("person_entity_id")
            )
            return await self.async_step_init()
        schema = vol.Schema(
            {
                vol.Required("name"): selector.TextSelector(),
                vol.Optional("person_entity_id"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="person")
                ),
            }
        )
        return self.async_show_form(step_id="add_member", data_schema=schema)

    async def async_step_remove_member(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not self._engine.members:
            return await self.async_step_init()
        if user_input is not None:
            self._engine.remove_member(user_input["member_id"])
            return await self.async_step_init()
        return self.async_show_form(
            step_id="remove_member",
            data_schema=vol.Schema(
                {vol.Required("member_id"): self._member_selector()}
            ),
        )

    # -- chores ------------------------------------------------------------

    async def async_step_add_chore(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._engine.create_chore(
                Chore(
                    name=user_input["name"],
                    assignee_id=user_input.get("assignee"),
                    description=user_input.get("description", ""),
                    recurrence=_recurrence_from_form(user_input),
                )
            )
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required("name"): selector.TextSelector(),
                vol.Optional("assignee"): self._member_selector(),
                vol.Required("frequency", default="daily"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=FREQUENCIES)
                ),
                vol.Optional("weekdays"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=v, label=l)
                            for v, l in _WEEKDAYS
                        ],
                        multiple=True,
                    )
                ),
                vol.Optional("day_of_month", default=1): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=31, mode="box")
                ),
                vol.Optional("interval", default=1): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=52, mode="box")
                ),
                vol.Optional("interval_unit", default="weeks"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=INTERVAL_UNITS)
                ),
                vol.Required("anchor_date"): selector.DateSelector(),
                vol.Required("due_time", default="09:00:00"): selector.TimeSelector(),
                vol.Optional("description"): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
            }
        )
        return self.async_show_form(step_id="add_chore", data_schema=schema)

    async def async_step_remove_chore(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not self._engine.chores:
            return await self.async_step_init()
        if user_input is not None:
            self._engine.delete_chore(user_input["chore_id"])
            return await self.async_step_init()
        options = [
            selector.SelectOptionDict(value=c.id, label=c.name)
            for c in self._engine.chores.values()
        ]
        return self.async_show_form(
            step_id="remove_chore",
            data_schema=vol.Schema(
                {
                    vol.Required("chore_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    # -- helpers -----------------------------------------------------------

    def _member_selector(self) -> selector.SelectSelector:
        options = [
            selector.SelectOptionDict(value=m.id, label=m.name)
            for m in self._engine.members.values()
        ]
        return selector.SelectSelector(
            selector.SelectSelectorConfig(options=options)
        )


def _coerce_time(value: Any) -> time:
    if isinstance(value, time):
        return value
    return time.fromisoformat(value)


def _coerce_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _recurrence_from_form(data: dict[str, Any]) -> Recurrence:
    frequency = data["frequency"]
    kwargs: dict[str, Any] = {
        "frequency": frequency,
        "due_time": _coerce_time(data["due_time"]),
        "anchor_date": _coerce_date(data["anchor_date"]),
    }
    if frequency == FREQ_WEEKLY:
        kwargs["weekdays"] = [int(d) for d in data.get("weekdays", [])]
    elif frequency == FREQ_MONTHLY:
        kwargs["day_of_month"] = int(data.get("day_of_month", 1))
    elif frequency == FREQ_INTERVAL:
        kwargs["interval"] = int(data.get("interval", 1))
        kwargs["interval_unit"] = data.get("interval_unit", "weeks")
    return Recurrence(**kwargs)
