"""An event entity per lock that fires once per unlock.

The unlock log is polled, so an event arrives within one refresh interval of
the unlock. Good for "who came in", not a doorbell.
"""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import EVENT_TYPE_UNLOCK
from .entity import TuyaLockEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(UnlockEvent(coordinator, device) for device in coordinator.devices.values())


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
