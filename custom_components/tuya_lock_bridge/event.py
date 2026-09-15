"""Event entities per lock.

- unlock: fires once per unlock, from the polled log (within seconds when push
  is on, otherwise within one refresh interval).
- ring and alarm: only with push, because a doorbell press and a wrong PIN
  never reach the unlock log. Without push they exist but stay silent.
"""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ALARM_TYPES, EVENT_TYPE_RING, EVENT_TYPE_UNLOCK
from .coordinator import SIGNAL_ALARM, SIGNAL_RING
from .entity import TuyaLockEntity

# What Tuya's `alarm_lock` enum looks like on the locks we know of, mapped to
# our event types. Anything else becomes "other" with the raw value attached.
ALARM_MAP = {
    "wrong_finger": "wrong_fingerprint",
    "wrong_password": "wrong_password",
    "wrong_card": "wrong_card",
    "wrong_face": "wrong_face",
    "tongue_bad": "lock_stuck",
    "too_hot": "other",
    "unclosed_time": "other",
    "tongue_not_out": "lock_stuck",
    "pry": "tamper",
    "key_in": "other",
    "low_battery": "low_battery",
    "power_off": "other",
    "shock": "tamper",
    "defense": "tamper",
    "hijack": "hijack",
}


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    entities = []
    for device in coordinator.devices.values():
        entities += [UnlockEvent(coordinator, device), RingEvent(coordinator, device), AlarmEvent(coordinator, device)]
    async_add_entities(entities)


class UnlockEvent(TuyaLockEntity, EventEntity):
    _attr_translation_key = "unlock"
    _attr_event_types = [EVENT_TYPE_UNLOCK]
    _attr_icon = "mdi:key-variant"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.device_id}_unlock"

    @callback
    def _handle_coordinator_update(self) -> None:
        # new_unlocks() only sets the watermark on its first call, so a
        # restart never replays the history into the logbook.
        for unlock in self.coordinator.new_unlocks(self.device.device_id):
            self._trigger_event(EVENT_TYPE_UNLOCK, {k: unlock[k] for k in ("who", "method", "key", "time")})
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Prime the watermark with whatever the first refresh brought in.
        self.coordinator.new_unlocks(self.device.device_id)


class _PushEvent(TuyaLockEntity, EventEntity):
    signal = ""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, f"{self.signal}_{self.device.device_id}", self._from_push))

    @callback
    def _from_push(self, value) -> None:
        raise NotImplementedError

    @property
    def extra_state_attributes(self) -> dict:
        return {"push": self.coordinator.push_status}


class RingEvent(_PushEvent):
    _attr_translation_key = "ring"
    _attr_event_types = [EVENT_TYPE_RING]
    _attr_icon = "mdi:bell-ring"
    signal = SIGNAL_RING

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.device_id}_ring"

    @callback
    def _from_push(self, value) -> None:
        self._trigger_event(EVENT_TYPE_RING, {"value": value})
        self.async_write_ha_state()


class AlarmEvent(_PushEvent):
    _attr_translation_key = "alarm"
    _attr_event_types = ALARM_TYPES
    _attr_icon = "mdi:shield-alert"
    signal = SIGNAL_ALARM

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.device_id}_alarm"

    @callback
    def _from_push(self, value) -> None:
        kind = ALARM_MAP.get(str(value), "other")
        self._trigger_event(kind, {"value": value})
        self.async_write_ha_state()
