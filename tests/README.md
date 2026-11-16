# Tests

```bash
pip install -r requirements_test.txt
python3 -m pytest tests/ -q
```

## Scope

These are **standalone unit tests** for the Home-Assistant-independent logic in
`models.py`: the `Recurrence` schedule math and all dataclass serialization.
`conftest.py` stubs the small slice of Home Assistant that `models.py`/`const.py`
import (`homeassistant.util.dt`, `homeassistant.const.Platform`) and exposes the
integration package as `ca`, so no Home Assistant install is required.

- `test_recurrence.py` - daily/weekly/monthly/interval next-due, month-end
  clamping, year rollover, anchor phasing, the two-phased-chores alternation
  scenario, and `iter_due` bounds.
- `test_models.py` - serialization round-trips for `Recurrence`, `Member`,
  `Chore`, `Occurrence`, plus `Occurrence.is_overdue` / `uid`.

## Not covered here

`coordinator.py` and the `todo` / `calendar` / `sensor` platforms and the
config/options flow are tightly coupled to the Home Assistant runtime (`Store`,
dispatcher, entity base classes, config-flow machinery). Test those with
[`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)
once the integration is loaded in a real HA test environment.
