"""Constants for the Chore Assistant integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "chore_assistant"

PLATFORMS: list[Platform] = [Platform.TODO, Platform.CALENDAR, Platform.SENSOR]

# Storage
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

# Dispatcher signal fired whenever engine state changes.
SIGNAL_UPDATE = f"{DOMAIN}_update"

# Hour of day (local) at which overdue chores are re-announced.
OVERDUE_CHECK_HOUR = 8

# Events emitted on the HA bus for user automations.
EVENT_DUE = f"{DOMAIN}_due"
EVENT_OVERDUE = f"{DOMAIN}_overdue"
EVENT_COMPLETED = f"{DOMAIN}_completed"
EVENT_REASSIGNED = f"{DOMAIN}_reassigned"

# Services
SERVICE_COMPLETE = "complete"
SERVICE_SKIP = "skip"
SERVICE_REASSIGN = "reassign"
SERVICE_CREATE_CHORE = "create_chore"
SERVICE_UPDATE_CHORE = "update_chore"
SERVICE_DELETE_CHORE = "delete_chore"

# Recurrence frequencies
FREQ_DAILY = "daily"
FREQ_WEEKLY = "weekly"
FREQ_MONTHLY = "monthly"
FREQ_INTERVAL = "interval"
FREQUENCIES = [FREQ_DAILY, FREQ_WEEKLY, FREQ_MONTHLY, FREQ_INTERVAL]

INTERVAL_UNIT_DAYS = "days"
INTERVAL_UNIT_WEEKS = "weeks"
INTERVAL_UNITS = [INTERVAL_UNIT_DAYS, INTERVAL_UNIT_WEEKS]

# Common attribute / field keys
ATTR_CHORE_ID = "chore_id"
ATTR_MEMBER_ID = "member_id"
ATTR_COMPLETED_BY = "completed_by"
ATTR_NAME = "name"
ATTR_ASSIGNEE = "assignee"
ATTR_DESCRIPTION = "description"
ATTR_FREQUENCY = "frequency"
ATTR_WEEKDAYS = "weekdays"
ATTR_DAY_OF_MONTH = "day_of_month"
ATTR_INTERVAL = "interval"
ATTR_INTERVAL_UNIT = "interval_unit"
ATTR_ANCHOR_DATE = "anchor_date"
ATTR_DUE_TIME = "due_time"
ATTR_PERSON_ENTITY_ID = "person_entity_id"
