"""Sensors: how many codes are valid right now, and who opened the door last."""

from __future__ import annotations

import time
from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CODES, DATA_UNLOCKS
from .coordinator import code_status
from .entity import TuyaLockEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    entities = []
    for device in coordinator.devices.values():
        entities.append(ValidCodesSensor(coordinator, device))
        entities.append(LastUnlockSensor(coordinator, device))
    async_add_entities(entities)


class ValidCodesSensor(TuyaLockEntity, SensorEntity):
    """Number of temporary codes valid at this moment; full list in attributes."""

    _attr_translation_key = "valid_codes"
    _attr_icon = "mdi:form-textbox-password"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "codes"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.device_id}_valid_codes"

    def _rows(self) -> tuple[list[dict], dict[str, int]]:
        now = int(time.time())
        rows, counts = [], {}
        for code in sorted(self.lock_data.get(DATA_CODES, []), key=lambda c: c.get("effective_time", 0), reverse=True):
            status = code_status(code, now)
            counts[status] = counts.get(status, 0) + 1
            if len(rows) < 25:  # the recorder truncates large attribute sets
                rows.append(
                    {
                        "id": code.get("id"),
                        "name": code.get("name"),
                        "from": datetime.fromtimestamp(code.get("effective_time", 0)).isoformat(timespec="minutes"),
                        "until": datetime.fromtimestamp(code.get("invalid_time", 0)).isoformat(timespec="minutes"),
                        "status": status,
                        "repeats": bool(code.get("schedule_list")),
                    }
                )
        return rows, counts

    @property
    def native_value(self) -> int:
        _, counts = self._rows()
        return counts.get("active", 0) + counts.get("waiting", 0)

    @property
    def extra_state_attributes(self) -> dict:
        rows, counts = self._rows()
        return {
            "codes": rows,
            "scheduled": counts.get("scheduled", 0),
            "expired": counts.get("expired", 0),
            "waiting_for_lock": counts.get("waiting", 0),
        }


class LastUnlockSensor(TuyaLockEntity, SensorEntity):
    """Who opened the door last, with the twenty unlocks before it."""

    _attr_translation_key = "last_unlock"
    _attr_icon = "mdi:door-open"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.device_id}_last_unlock"

    @property
    def native_value(self) -> str | None:
        unlocks = self.lock_data.get(DATA_UNLOCKS, [])
        return unlocks[0]["who"] if unlocks else None

    @property
    def extra_state_attributes(self) -> dict:
        unlocks = self.lock_data.get(DATA_UNLOCKS, [])
        if not unlocks:
            return {}
        latest = unlocks[0]
        return {
            "method": latest["method"],
            "key": latest["key"],
            "time": latest["time"],
            "recent": [{k: u[k] for k in ("who", "method", "key", "time")} for u in unlocks],
        }
