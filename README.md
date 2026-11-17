# Chore Assistant

A Home Assistant custom integration for managing household chores natively, targeted to how my family handles chores at the moment.

## Features (v1)

- **Chores** are recurring definitions (what, who, how often, start date, notes).
- **Occurrences** are the due-able instances you actually complete. Exactly one
  is open per chore at a time; an overdue one stays visible rather than piling up.
- **Recurrence**: daily, weekly (chosen weekdays), monthly (chosen day), or every
  N days/weeks, each with an explicit start/anchor date. A chore is due on a
  *date* — there is no time of day, it just needs doing sometime that day, and
  it only counts as overdue once the date has passed. Next due is always
  schedule-anchored, never based on when you completed it.
- **Members** are the people who do chores; each links to a Home Assistant
  `person` for presence and notifications.
- **Entities**: a unified **Chores** todo list and one per member, a dedicated
  **Chores calendar**, and a per-member overdue sensor.
- **Services**: `complete`, `skip`, `reassign`, `create_chore`, `update_chore`,
  `delete_chore`.
- **Events** for your own automations: `chore_assistant_due`, `_overdue`,
  `_completed`, `_reassigned` (each carries the chore and the member's `person`),
  plus an included overdue-reminder blueprint.

## Installation (HACS)

1. In HACS, add this repository as a custom repository (category: Integration).
2. Install **Chore Assistant** and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration → Chore Assistant**.
4. Open the integration's **Configure** menu to add members and chores.
