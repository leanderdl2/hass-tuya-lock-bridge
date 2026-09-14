"""Tuya Lock Bridge: control Tuya smart locks and manage their access codes."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import TuyaAuthError, TuyaDevice, TuyaLockApi, TuyaLockError
from .const import CONF_ACCESS_ID, CONF_ACCESS_SECRET, CONF_ENDPOINT, CONF_LOCKS, PLATFORMS
from .coordinator import TuyaLockCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

type TuyaLockConfigEntry = ConfigEntry[TuyaLockCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TuyaLockConfigEntry) -> bool:
    api = TuyaLockApi(entry.data[CONF_ENDPOINT], entry.data[CONF_ACCESS_ID], entry.data[CONF_ACCESS_SECRET])

    try:
        listed = await hass.async_add_executor_job(api.list_devices)
    except TuyaAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except TuyaLockError as err:
        raise ConfigEntryNotReady(str(err)) from err

    wanted = set(entry.options.get(CONF_LOCKS, []))
    devices = {d.device_id: d for d in listed if d.device_id in wanted}
    # A configured lock that Tuya no longer lists still gets a device, so its
    # entities show as unavailable rather than vanishing without a word.
    for device_id in wanted - set(devices):
        _LOGGER.warning("Lock %s is configured but not listed by Tuya any more", device_id)
        devices[device_id] = TuyaDevice(device_id=device_id, name=device_id, category="", product_name="", online=False)

    coordinator = TuyaLockCoordinator(hass, entry, api, devices)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: TuyaLockConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TuyaLockConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
