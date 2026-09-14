"""A switch per profile: on means its codes and cards open the door.

Profiles come and go, so the platform watches the coordinator and adds a
switch for every profile it has not seen before. App accounts that share the
lock get no switch: those are managed in the Tuya app, and Tuya refuses
schedule changes on them from the API.
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import TuyaLockError
from .const import DATA_MEMBERS
from .entity import TuyaLockEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    known: dict[tuple[str, str], str] = {}  # (device, user) -> unique_id
    registry = er.async_get(hass)

    @callback
    def _sync() -> None:
        new = []
        present: set[tuple[str, str]] = set()
        for device_id, device in coordinator.devices.items():
            for member in (coordinator.data or {}).get(device_id, {}).get(DATA_MEMBERS, []):
                if member.get("home_user"):
                    continue
                key = (device_id, member["user_id"])
                present.add(key)
                if key not in known:
                    switch = ProfileSwitch(coordinator, device, member["user_id"])
                    known[key] = switch.unique_id
                    new.append(switch)
        if new:
            async_add_entities(new)
        # A profile that is gone takes its switch with it, rather than leaving
        # an unavailable entity behind forever. Checked against the registry,
        # not just this run's memory, so a switch left over from before a
        # restart is cleaned up too - and its entity_id freed for a new
        # profile with the same name.
        wanted = {f"{d}_profile_{u}" for d, u in present}
        for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if reg_entry.domain != "switch" or reg_entry.unique_id in wanted:
                continue
            device_id = reg_entry.unique_id.split("_profile_", 1)[0]
            if coordinator.data and device_id in coordinator.data:
                registry.async_remove(reg_entry.entity_id)
        for key in list(known):
            if key not in present:
                known.pop(key)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))


class ProfileSwitch(TuyaLockEntity, SwitchEntity):
    _attr_translation_key = "profile"
    _attr_icon = "mdi:account-key"

    def __init__(self, coordinator, device, user_id: str) -> None:
        super().__init__(coordinator, device)
        self.user_id = user_id
        self._attr_unique_id = f"{device.device_id}_profile_{user_id}"

    @property
    def _member(self) -> dict | None:
        return next((m for m in self.lock_data.get(DATA_MEMBERS, []) if m.get("user_id") == self.user_id), None)

    @property
    def available(self) -> bool:
        # A deleted profile makes its switch unavailable rather than lying.
        return super().available and self._member is not None

    @property
    def translation_placeholders(self) -> dict[str, str]:
        member = self._member
        return {"name": member["name"] if member else self.user_id}

    @property
    def is_on(self) -> bool | None:
        member = self._member
        return None if member is None else bool(member.get("active", True))

    @property
    def extra_state_attributes(self) -> dict:
        member = self._member
        if not member:
            return {}
        return {
            "user_id": self.user_id,
            "methods": [{"type": m["type"], "name": m["name"], "sn": m["sn"]} for m in member.get("methods", [])],
        }

    async def _set(self, active: bool) -> None:
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.api.set_member_active, self.device.device_id, self.user_id, active
            )
        except TuyaLockError as err:
            raise HomeAssistantError(str(err)) from err
        # Show the new state at once, then confirm it from Tuya. A debounced
        # request_refresh would leave the switch on the old state for ten
        # seconds after the user flipped it.
        member = self._member
        if member is not None:
            member["active"] = active
            self.async_write_ha_state()
        await self.coordinator.async_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)
