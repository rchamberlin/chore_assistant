"""The Chore Assistant integration."""

from __future__ import annotations

from datetime import date

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_ASSIGNEE,
    ATTR_CHORE_ID,
    ATTR_COMPLETED_BY,
    ATTR_DESCRIPTION,
    ATTR_MEMBER_ID,
    ATTR_NAME,
    DOMAIN,
    PLATFORMS,
    SERVICE_COMPLETE,
    SERVICE_CREATE_CHORE,
    SERVICE_DELETE_CHORE,
    SERVICE_REASSIGN,
    SERVICE_SKIP,
    SERVICE_UPDATE_CHORE,
)
from .coordinator import ChoreEngine
from .models import Chore, Recurrence

ChoreConfigEntry = ConfigEntry[ChoreEngine]


async def async_setup_entry(hass: HomeAssistant, entry: ChoreConfigEntry) -> bool:
    """Set up Chore Assistant from a config entry."""
    engine = ChoreEngine(hass)
    await engine.async_load()
    entry.runtime_data = engine

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass, engine)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ChoreConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data.async_shutdown()
        for service in (
            SERVICE_COMPLETE,
            SERVICE_SKIP,
            SERVICE_REASSIGN,
            SERVICE_CREATE_CHORE,
            SERVICE_UPDATE_CHORE,
            SERVICE_DELETE_CHORE,
        ):
            hass.services.async_remove(DOMAIN, service)
    return unload_ok


def _async_register_services(hass: HomeAssistant, engine: ChoreEngine) -> None:
    """Register the chore_assistant.* services."""

    async def _complete(call: ServiceCall) -> None:
        engine.complete(call.data[ATTR_CHORE_ID], call.data.get(ATTR_COMPLETED_BY))

    async def _skip(call: ServiceCall) -> None:
        engine.skip(call.data[ATTR_CHORE_ID])

    async def _reassign(call: ServiceCall) -> None:
        engine.reassign(call.data[ATTR_CHORE_ID], call.data.get(ATTR_MEMBER_ID))

    async def _create_chore(call: ServiceCall) -> None:
        engine.create_chore(
            Chore(
                name=call.data[ATTR_NAME],
                assignee_id=call.data.get(ATTR_ASSIGNEE),
                description=call.data.get(ATTR_DESCRIPTION, ""),
                recurrence=_recurrence_from_service(call.data),
            )
        )

    async def _update_chore(call: ServiceCall) -> None:
        changes: dict = {
            k: call.data.get(k)
            for k in (ATTR_NAME, ATTR_ASSIGNEE, ATTR_DESCRIPTION)
            if k in call.data
        }
        if ATTR_ASSIGNEE in changes:
            changes["assignee_id"] = changes.pop(ATTR_ASSIGNEE)
        engine.update_chore(call.data[ATTR_CHORE_ID], changes)

    async def _delete_chore(call: ServiceCall) -> None:
        engine.delete_chore(call.data[ATTR_CHORE_ID])

    chore_ref = {vol.Required(ATTR_CHORE_ID): cv.string}

    hass.services.async_register(
        DOMAIN, SERVICE_COMPLETE, _complete,
        schema=vol.Schema({**chore_ref, vol.Optional(ATTR_COMPLETED_BY): cv.string}),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SKIP, _skip, schema=vol.Schema(chore_ref)
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REASSIGN, _reassign,
        schema=vol.Schema({**chore_ref, vol.Optional(ATTR_MEMBER_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_CHORE, _create_chore,
        schema=vol.Schema(
            {
                vol.Required(ATTR_NAME): cv.string,
                vol.Optional(ATTR_ASSIGNEE): cv.string,
                vol.Optional(ATTR_DESCRIPTION): cv.string,
                vol.Optional("frequency"): cv.string,
                vol.Optional("anchor_date"): cv.date,
                vol.Optional("weekdays"): [vol.Coerce(int)],
                vol.Optional("day_of_month"): vol.All(int, vol.Range(1, 31)),
                vol.Optional("interval"): vol.All(int, vol.Range(1, 365)),
                vol.Optional("interval_unit"): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_CHORE, _update_chore,
        schema=vol.Schema(
            {
                **chore_ref,
                vol.Optional(ATTR_NAME): cv.string,
                vol.Optional(ATTR_ASSIGNEE): cv.string,
                vol.Optional(ATTR_DESCRIPTION): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_CHORE, _delete_chore, schema=vol.Schema(chore_ref)
    )


def _recurrence_from_service(data: dict) -> Recurrence:
    kwargs: dict = {}
    if (freq := data.get("frequency")) is not None:
        kwargs["frequency"] = freq
    if isinstance(data.get("anchor_date"), date):
        kwargs["anchor_date"] = data["anchor_date"]
    for key in ("weekdays", "day_of_month", "interval", "interval_unit"):
        if data.get(key) is not None:
            kwargs[key] = data[key]
    return Recurrence(**kwargs)
