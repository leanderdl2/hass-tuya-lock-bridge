"""Tuya Lock Bridge: control Tuya smart locks and manage their access codes."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import TuyaAuthError, TuyaDevice, TuyaLockApi, TuyaLockError
from .const import CONF_ACCESS_ID, CONF_ACCESS_SECRET, CONF_ENDPOINT, CONF_LOCKS, DOMAIN, PLATFORMS
from .coordinator import TuyaLockCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

type TuyaLockConfigEntry = ConfigEntry[TuyaLockCoordinator]

PANEL_URL_PATH = "tuya-lock-bridge"
PANEL_SCRIPT_URL = "/tuya_lock_bridge/panel.js"


async def _async_register_panel(hass: HomeAssistant) -> None:
    """A page in the sidebar to manage codes and profiles by hand.

    A custom panel: a web component served by this integration that talks to
    Home Assistant over its own WebSocket connection, so it shares Home
    Assistant's authentication and needs no port or token of its own. Only for
    administrators - it opens doors.
    """
    store = hass.data.setdefault(DOMAIN, {})
    if not store.get("static"):
        script = Path(__file__).parent / "panel" / "tuya-lock-bridge-panel.js"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_SCRIPT_URL, str(script), cache_headers=False)]
        )
        store["static"] = True
    if store.get("panel"):
        return
    from .const import VERSION  # noqa: PLC0415 - keeps the import cheap at module load

    frontend.async_register_built_in_panel(
        hass,
        "custom",
        sidebar_title="Sloten" if (hass.config.language or "").startswith("nl") else "Locks",
        sidebar_icon="mdi:lock-smart",
        frontend_url_path=PANEL_URL_PATH,
        config={
            "_panel_custom": {
                "name": "tuya-lock-bridge-panel",
                # The version in the URL makes browsers fetch a fresh copy
                # after an update instead of serving the cached one.
                "module_url": f"{PANEL_SCRIPT_URL}?v={VERSION}",
                "embed_iframe": False,
                "trust_external": False,
            }
        },
        require_admin=True,
    )
    store["panel"] = True


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
    await coordinator.async_load_stats()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    coordinator.start_push()
    entry.async_on_unload(coordinator.stop_push)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_services(hass)
    await _async_register_panel(hass)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: TuyaLockConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TuyaLockConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # The panel belongs to the integration, not to one entry: keep it while
    # another entry is still loaded.
    others = [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id and e.state.recoverable]
    if ok and not others and hass.data.get(DOMAIN, {}).get("panel"):
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
        hass.data[DOMAIN]["panel"] = False
    return ok
