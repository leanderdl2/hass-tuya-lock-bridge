"""Base entity: one Home Assistant device per lock."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import TuyaDevice
from .const import DOMAIN
from .coordinator import TuyaLockCoordinator


class TuyaLockEntity(CoordinatorEntity[TuyaLockCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TuyaLockCoordinator, device: TuyaDevice) -> None:
        super().__init__(coordinator)
        self.device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer="Tuya",
            model=device.product_name or device.category,
        )

    @property
    def lock_data(self) -> dict:
        return (self.coordinator.data or {}).get(self.device.device_id, {})

    @property
    def available(self) -> bool:
        return super().available and self.device.device_id in (self.coordinator.data or {})
