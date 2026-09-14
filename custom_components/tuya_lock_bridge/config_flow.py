"""Config flow: credentials, then pick the locks from the account."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import TuyaAuthError, TuyaDevice, TuyaLockApi, TuyaLockError
from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_ENDPOINT,
    CONF_LOCKS,
    CONF_REFRESH_MINUTES,
    DEFAULT_REFRESH_MINUTES,
    DOMAIN,
    ENDPOINTS,
)

_LOGGER = logging.getLogger(__name__)


def _device_options(devices: list[TuyaDevice]) -> list[selector.SelectOptionDict]:
    """Locks first; if the account has none in a lock category, show everything
    so a lock in a category we do not know about can still be picked."""
    locks = [d for d in devices if d.is_lock]
    shown = locks or devices
    return [
        selector.SelectOptionDict(
            value=d.device_id,
            label=f"{d.name} ({d.product_name or d.category})" + ("" if d.online else " - offline"),
        )
        for d in sorted(shown, key=lambda d: d.name.lower())
    ]


class TuyaLockBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Two steps: account, then locks."""

    VERSION = 1

    def __init__(self) -> None:
        self._credentials: dict[str, Any] = {}
        self._devices: list[TuyaDevice] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            api = TuyaLockApi(user_input[CONF_ENDPOINT], user_input[CONF_ACCESS_ID], user_input[CONF_ACCESS_SECRET])
            try:
                self._devices = await self.hass.async_add_executor_job(api.list_devices)
            except TuyaAuthError:
                errors["base"] = "invalid_auth"
            except TuyaLockError as err:
                _LOGGER.warning("Tuya refused the device list: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error talking to Tuya")
                errors["base"] = "unknown"
            else:
                if not self._devices:
                    errors["base"] = "no_devices"
                else:
                    await self.async_set_unique_id(user_input[CONF_ACCESS_ID])
                    self._abort_if_unique_id_configured()
                    self._credentials = user_input
                    return await self.async_step_locks()

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCESS_ID): str,
                vol.Required(CONF_ACCESS_SECRET): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_ENDPOINT, default="https://openapi.tuyaeu.com"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=k, label=f"{v} ({k})") for k, v in ENDPOINTS.items()],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_locks(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_LOCKS):
                errors["base"] = "no_locks"
            else:
                return self.async_create_entry(
                    title="Tuya Lock Bridge",
                    data=self._credentials,
                    options={CONF_LOCKS: user_input[CONF_LOCKS], CONF_REFRESH_MINUTES: DEFAULT_REFRESH_MINUTES},
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_LOCKS, default=[d.device_id for d in self._devices if d.is_lock]): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=_device_options(self._devices), multiple=True)
                )
            }
        )
        return self.async_show_form(step_id="locks", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    """Change the locks or the refresh interval later."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        entry = self.config_entry
        api = TuyaLockApi(entry.data[CONF_ENDPOINT], entry.data[CONF_ACCESS_ID], entry.data[CONF_ACCESS_SECRET])
        try:
            devices = await self.hass.async_add_executor_job(api.list_devices)
        except TuyaLockError:
            devices = []

        if user_input is not None:
            if not user_input.get(CONF_LOCKS):
                errors["base"] = "no_locks"
            else:
                return self.async_create_entry(title="", data=user_input)

        current = entry.options.get(CONF_LOCKS, [])
        # Keep a lock that Tuya no longer lists selectable, so it is not
        # silently dropped by an options change.
        options = _device_options(devices)
        known = {o["value"] for o in options}
        options += [selector.SelectOptionDict(value=d, label=f"{d} (no longer listed)") for d in current if d not in known]

        schema = vol.Schema(
            {
                vol.Required(CONF_LOCKS, default=current): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, multiple=True)
                ),
                vol.Required(
                    CONF_REFRESH_MINUTES, default=entry.options.get(CONF_REFRESH_MINUTES, DEFAULT_REFRESH_MINUTES)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=120, step=1, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
