"""Services: everything the panel of the add-on could do, as Home Assistant
actions - selectable in the automation editor, and answering with data so an
automation can read the id of the code it just created."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import dt as dt_util

from .api import TuyaLockError, build_schedule
from .const import DATA_MEMBERS, DOMAIN
from .coordinator import TuyaLockCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = "device_id"

SCHEMA_DEVICE = vol.Schema({vol.Required(ATTR_DEVICE): cv.string})
SCHEMA_CODE = SCHEMA_DEVICE.extend({vol.Required("code_id"): vol.Coerce(int)})
SCHEMA_CREATE_CODE = SCHEMA_DEVICE.extend(
    {
        vol.Required("password"): cv.string,
        vol.Required("start"): cv.datetime,
        vol.Required("end"): cv.datetime,
        vol.Optional("name"): cv.string,
        vol.Optional("one_time", default=False): cv.boolean,
        vol.Optional("days"): vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(1, 7))]),
        vol.Optional("daily_from"): cv.string,
        vol.Optional("daily_until"): cv.string,
    }
)
SCHEMA_BOOK = SCHEMA_DEVICE.extend(
    {
        vol.Required("last4"): cv.string,
        vol.Required("checkin"): cv.datetime,
        vol.Required("checkout"): cv.datetime,
        vol.Optional("name"): cv.string,
    }
)
SCHEMA_ADD_PROFILE = SCHEMA_DEVICE.extend({vol.Required("name"): cv.string, vol.Required("password"): cv.string})
SCHEMA_PROFILE = SCHEMA_DEVICE.extend({vol.Required("user_id"): cv.string})
SCHEMA_ADD_METHOD = SCHEMA_PROFILE.extend(
    {
        vol.Required("type"): vol.In(["password", "card", "fingerprint", "face"]),
        vol.Optional("password"): cv.string,
        vol.Optional("name"): cv.string,
    }
)
SCHEMA_METHOD = SCHEMA_PROFILE.extend(
    {vol.Required("type"): vol.In(["password", "card", "fingerprint", "face"]), vol.Required("sn"): vol.Coerce(int)}
)
SCHEMA_RENAME = SCHEMA_METHOD.extend({vol.Required("name"): cv.string})


def _resolve(hass: HomeAssistant, ha_device_id: str) -> tuple[TuyaLockCoordinator, str]:
    """A Home Assistant device id -> (its coordinator, the Tuya device id)."""
    device = dr.async_get(hass).async_get(ha_device_id)
    if device is None:
        raise ServiceValidationError(f"unknown device {ha_device_id}")
    tuya_id = next((ident[1] for ident in device.identifiers if ident[0] == DOMAIN), None)
    if tuya_id is None:
        raise ServiceValidationError("that device is not a Tuya Lock Bridge lock")
    for entry in hass.config_entries.async_entries(DOMAIN):
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator and tuya_id in coordinator.devices:
            return coordinator, tuya_id
    raise ServiceValidationError("that lock is not configured any more")


def _ts(value: datetime) -> int:
    """A datetime without a zone - what a datetime-local field produces - is
    Home Assistant's local time, not the container's, which is usually UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return int(value.timestamp())


async def _run(hass: HomeAssistant, coordinator: TuyaLockCoordinator, func, *args) -> Any:
    try:
        return await hass.async_add_executor_job(func, *args)
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err
    except TuyaLockError as err:
        raise HomeAssistantError(str(err)) from err


def async_setup_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "unlock"):
        return

    async def unlock(call: ServiceCall) -> None:
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        await _run(hass, coordinator, coordinator.api.unlock, device_id, coordinator.devices[device_id].category)

    async def create_code(call: ServiceCall) -> ServiceResponse:
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        d = call.data
        schedule = None
        if d.get("days"):
            schedule = build_schedule(d["days"], d.get("daily_from", "00:00"), d.get("daily_until", "23:59"))
        name = d.get("name") or f"Code-{d['password'][-4:]}"
        code_id = await _run(
            hass,
            coordinator,
            lambda: coordinator.api.create_code(
                device_id,
                d["password"],
                name,
                _ts(d["start"]),
                _ts(d["end"]),
                one_time=d["one_time"],
                schedule=schedule,
                time_zone=hass.config.time_zone,
            ),
        )
        await coordinator.async_refresh()
        return {"code_id": code_id, "name": name}

    async def book(call: ServiceCall) -> ServiceResponse:
        """A code per booking: the two-digit year of check-in plus the last
        four digits of the guest's phone number. Six digits, which is what
        most keypads expect."""
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        d = call.data
        last4 = str(d["last4"]).strip()[-4:].zfill(4)
        if not last4.isdigit():
            raise ServiceValidationError("last4 must be four digits")
        pin = d["checkin"].strftime("%y") + last4
        name = d.get("name") or f"Booking-{last4}"
        code_id = await _run(
            hass,
            coordinator,
            lambda: coordinator.api.create_code(device_id, pin, name, _ts(d["checkin"]), _ts(d["checkout"])),
        )
        await coordinator.async_refresh()
        return {"code_id": code_id, "name": name}

    async def revoke_code(call: ServiceCall) -> None:
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        await _run(hass, coordinator, coordinator.api.revoke_code, device_id, call.data["code_id"])
        await coordinator.async_refresh()

    async def purge_code(call: ServiceCall) -> None:
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        await _run(hass, coordinator, coordinator.api.purge_code, device_id, call.data["code_id"])
        await coordinator.async_refresh()

    async def list_codes(call: ServiceCall) -> ServiceResponse:
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        codes = await _run(hass, coordinator, coordinator.api.list_codes, device_id)
        return {"codes": codes}

    async def add_profile(call: ServiceCall) -> ServiceResponse:
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        name, password = call.data["name"].strip(), call.data["password"].strip()

        def _do() -> dict[str, Any]:
            uid = coordinator.api.create_member(device_id, name)
            try:
                sn = coordinator.api.enrol_method(device_id, uid, "password", password, name)
            except Exception:
                coordinator.api.delete_member(device_id, uid)
                raise
            return {"user_id": uid, "sn": sn}

        result = await _run(hass, coordinator, _do)
        await coordinator.async_refresh()
        return result

    async def delete_profile(call: ServiceCall) -> None:
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        uid = call.data["user_id"]

        def _do() -> None:
            member = next(
                (m for m in coordinator.data.get(device_id, {}).get(DATA_MEMBERS, []) if m["user_id"] == uid), None
            )
            if member is None:
                raise ValueError(f"unknown profile {uid}")
            if member.get("home_user"):
                raise ValueError("this is an app account that shares the lock - remove it in the Tuya app")
            for m in member.get("methods", []):
                coordinator.api.delete_method(device_id, uid, m["type"], m["sn"])
            coordinator.api.delete_member(device_id, uid)

        await _run(hass, coordinator, _do)
        await coordinator.async_refresh()

    async def add_method(call: ServiceCall) -> ServiceResponse:
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        d = call.data
        sn = await _run(
            hass,
            coordinator,
            lambda: coordinator.api.enrol_method(device_id, d["user_id"], d["type"], d.get("password"), d.get("name")),
        )
        await coordinator.async_refresh()
        return {"sn": sn, "pending": sn is None}

    async def rename_method(call: ServiceCall) -> None:
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        d = call.data
        await _run(hass, coordinator, coordinator.api.rename_method, device_id, d["type"], d["sn"], d["name"])
        await coordinator.async_refresh()

    async def delete_method(call: ServiceCall) -> None:
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        d = call.data
        await _run(hass, coordinator, coordinator.api.delete_method, device_id, d["user_id"], d["type"], d["sn"])
        await coordinator.async_refresh()

    async def list_profiles(call: ServiceCall) -> ServiceResponse:
        coordinator, device_id = _resolve(hass, call.data[ATTR_DEVICE])
        return {"profiles": coordinator.data.get(device_id, {}).get(DATA_MEMBERS, [])}

    async def refresh(call: ServiceCall) -> None:
        coordinator, _ = _resolve(hass, call.data[ATTR_DEVICE])
        await coordinator.async_refresh()

    reg = hass.services.async_register
    reg(DOMAIN, "unlock", unlock, schema=SCHEMA_DEVICE)
    reg(DOMAIN, "create_code", create_code, schema=SCHEMA_CREATE_CODE, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "book", book, schema=SCHEMA_BOOK, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "revoke_code", revoke_code, schema=SCHEMA_CODE)
    reg(DOMAIN, "purge_code", purge_code, schema=SCHEMA_CODE)
    reg(DOMAIN, "list_codes", list_codes, schema=SCHEMA_DEVICE, supports_response=SupportsResponse.ONLY)
    reg(DOMAIN, "add_profile", add_profile, schema=SCHEMA_ADD_PROFILE, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "delete_profile", delete_profile, schema=SCHEMA_PROFILE)
    reg(DOMAIN, "add_method", add_method, schema=SCHEMA_ADD_METHOD, supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "rename_method", rename_method, schema=SCHEMA_RENAME)
    reg(DOMAIN, "delete_method", delete_method, schema=SCHEMA_METHOD)
    reg(DOMAIN, "list_profiles", list_profiles, schema=SCHEMA_DEVICE, supports_response=SupportsResponse.ONLY)
    reg(DOMAIN, "refresh", refresh, schema=SCHEMA_DEVICE)
