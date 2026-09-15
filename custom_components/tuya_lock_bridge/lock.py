"""A lock entity per lock, so Home Assistant's own lock card, voice assistants
and Google/Alexa exposure work.

A Tuya keypad reports no lock state to the cloud, so the entity is an
"assumed state" one: it shows Unknown at rest, Opening while the command is
under way, Open for a few seconds afterwards, then Unknown again. Locking is
not a thing it can do - the strike relocks on its own - so the lock service
answers with an error rather than pretending.
"""

from __future__ import annotations

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .api import TuyaLockError
from .const import DOMAIN
from .entity import TuyaLockEntity

OPEN_SECONDS = 5


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(DoorLock(coordinator, device) for device in coordinator.devices.values())


class DoorLock(TuyaLockEntity, LockEntity):
    _attr_translation_key = "door"
    _attr_supported_features = LockEntityFeature.OPEN
    _attr_assumed_state = True
    _attr_is_locked = None

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.device_id}_lock"
        self._cancel_reset = None

    async def async_open(self, **kwargs) -> None:
        await self._open()

    async def async_unlock(self, **kwargs) -> None:
        await self._open()

    async def async_lock(self, **kwargs) -> None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="cannot_lock")

    async def _open(self) -> None:
        self._attr_is_opening = True
        self.async_write_ha_state()
        try:
            await self.hass.async_add_executor_job(self.coordinator.api.unlock, self.device.device_id, self.device.category)
        except TuyaLockError as err:
            self._attr_is_opening = False
            self.async_write_ha_state()
            raise HomeAssistantError(str(err)) from err
        self._attr_is_opening = False
        self._attr_is_open = True
        self.async_write_ha_state()
        if self._cancel_reset is not None:
            self._cancel_reset()
        self._cancel_reset = async_call_later(self.hass, OPEN_SECONDS, self._reset)

    async def _reset(self, _now) -> None:
        self._cancel_reset = None
        self._attr_is_open = False
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._cancel_reset is not None:
            self._cancel_reset()
        await super().async_will_remove_from_hass()
