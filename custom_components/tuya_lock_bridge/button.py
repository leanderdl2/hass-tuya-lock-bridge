"""A button per lock that opens the door."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import TuyaLockError
from .entity import TuyaLockEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(OpenDoorButton(coordinator, device) for device in coordinator.devices.values())


class OpenDoorButton(TuyaLockEntity, ButtonEntity):
    _attr_translation_key = "open"
    _attr_icon = "mdi:door-open"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.device_id}_open"

    async def async_press(self) -> None:
        try:
            await self.hass.async_add_executor_job(self.coordinator.api.unlock, self.device.device_id, self.device.category)
        except TuyaLockError as err:
            raise HomeAssistantError(str(err)) from err
        # self._context is the service call's context: it carries the user.
        await self.coordinator.async_record(self._context, "unlock", self.device.device_id)
