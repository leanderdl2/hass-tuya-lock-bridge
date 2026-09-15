"""Polls Tuya for every configured lock and holds the result.

One coordinator per config entry. Each refresh fetches, per lock, the temporary
codes, the recent unlock log and the members with their permanent methods. That
is roughly 3 + N calls per lock (N = members) against the Tuya project's
monthly allowance, so the interval is configurable and defaults to five
minutes.

The coordinator also owns the optional push listener: a message about a lock
triggers a refresh a few seconds later, so an unlock shows up almost at once
instead of at the next interval, and doorbell and alarm messages are handed to
the event entities directly.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    LOG_METHODS,
    TuyaAuthError,
    TuyaDevice,
    TuyaLockApi,
    TuyaLockError,
    TuyaNotAuthorisedError,
    TuyaSubscriptionError,
    temporary_slot,
)
from .const import (
    BUS_EVENT_PUSH,
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_ENDPOINT,
    CONF_LOCKS,
    CONF_PUSH,
    CONF_PUSH_ENV,
    CONF_REFRESH_MINUTES,
    CONF_SUBSCRIPTION_END,
    DATA_CODES,
    DATA_MEMBERS,
    DATA_UNLOCKS,
    DEFAULT_REFRESH_MINUTES,
    DOMAIN,
    ISSUE_API_NOT_AUTHORISED,
    ISSUE_PUSH_UNAVAILABLE,
    ISSUE_SUBSCRIPTION_EXPIRED,
    ISSUE_SUBSCRIPTION_EXPIRING,
    PULSAR_HOSTS,
    PUSH_ENV_PRODUCTION,
)
from .push import TuyaPushListener

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
# Seconds between a push message about a lock and the refresh it triggers:
# Tuya writes the unlock log a moment after the status report.
PUSH_REFRESH_DELAY = 3
EXPIRY_WARNING_DAYS = 30

SIGNAL_RING = f"{DOMAIN}_ring"
SIGNAL_ALARM = f"{DOMAIN}_alarm"


def code_status(code: dict[str, Any], now: int) -> str:
    """Same rules as everywhere else: revoked by phase, expired/scheduled by
    the times (phases flip once a code has expired), pending by phase 12."""
    if code.get("phase") == 17:
        return "revoked"
    if code.get("invalid_time", 0) < now:
        return "expired"
    if code.get("effective_time", 0) > now:
        return "scheduled"
    if code.get("phase") == 12:
        return "waiting"
    return "active"


def summarise_unlock(log: dict[str, Any], codes_by_sn: dict[int, str]) -> dict[str, Any]:
    status = log.get("status") or {}
    method_code = status.get("code") or ""
    method = LOG_METHODS.get(method_code, method_code)
    who = (log.get("unlock_name") or "").strip() or (log.get("nick_name") or "").strip()
    if method == "temporary":
        sn = temporary_slot(status.get("value"))
        if sn in codes_by_sn:
            who = codes_by_sn[sn]
    stamp = int(log.get("update_time", 0)) // 1000
    return {
        "who": who or method or "?",
        "method": method,
        "key": status.get("value"),
        "time": datetime.fromtimestamp(stamp).isoformat(timespec="seconds"),
        "timestamp": stamp,
    }


class TuyaLockCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """data[device_id] = {"codes": [...], "unlocks": [...], "members": [...]}"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: TuyaLockApi, devices: dict[str, TuyaDevice]) -> None:
        minutes = int(entry.options.get(CONF_REFRESH_MINUTES, DEFAULT_REFRESH_MINUTES))
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=timedelta(minutes=max(1, minutes)))
        self.entry = entry
        self.api = api
        self.devices = devices  # device_id -> TuyaDevice, only the configured locks
        # Newest unlock timestamp seen per lock, so the event entity fires only
        # for unlocks that happened after the previous refresh - and never
        # replays the whole history after a restart.
        self.last_seen: dict[str, int] = {}
        # API calls this month, persisted so a restart does not reset the count.
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.calls_month = ""
        self.calls = 0
        self.push: TuyaPushListener | None = None
        self.push_connected = False
        self.push_status = "off"
        self._pending_refresh: dict[str, Any] = {}

    @property
    def lock_ids(self) -> list[str]:
        return list(self.entry.options.get(CONF_LOCKS, []))

    # --------------------------------------------------------------- polling

    def _fetch_one(self, device_id: str) -> dict[str, Any]:
        codes = self.api.list_codes(device_id)
        codes_by_sn = {c.get("sn"): c.get("name") for c in codes if c.get("sn")}
        unlocks = sorted(
            (summarise_unlock(entry, codes_by_sn) for entry in self.api.unlock_log(device_id)),
            key=lambda u: u["timestamp"],
            reverse=True,
        )
        members = self.api.list_members(device_id)
        return {DATA_CODES: codes, DATA_UNLOCKS: unlocks, DATA_MEMBERS: members}

    def _fetch_all(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for device_id in self.lock_ids:
            try:
                out[device_id] = self._fetch_one(device_id)
            except (TuyaSubscriptionError, TuyaNotAuthorisedError):
                raise
            except TuyaLockError as err:
                # One lock failing must not blank the others; keep the last
                # known data for it and log why.
                _LOGGER.warning("Refresh failed for %s: %s", device_id, err)
                if self.data and device_id in self.data:
                    out[device_id] = self.data[device_id]
        return out

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            data = await self.hass.async_add_executor_job(self._fetch_all)
        except TuyaSubscriptionError as err:
            self._issue(ISSUE_SUBSCRIPTION_EXPIRED, ir.IssueSeverity.ERROR, {"message": str(err)})
            raise UpdateFailed(f"Tuya's cloud development plan for this project has expired: {err}") from err
        except TuyaNotAuthorisedError as err:
            self._issue(ISSUE_API_NOT_AUTHORISED, ir.IssueSeverity.ERROR, {"message": str(err)})
            raise UpdateFailed(f"the project is not authorised for this API: {err}") from err
        except TuyaAuthError as err:
            raise UpdateFailed(f"Tuya refused the credentials: {err}") from err
        except TuyaLockError as err:
            raise UpdateFailed(str(err)) from err
        finally:
            await self._async_save_stats()
        # A successful round means the plan and the authorisation are fine.
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_SUBSCRIPTION_EXPIRED)
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_API_NOT_AUTHORISED)
        self._check_expiry_warning()
        return data

    def new_unlocks(self, device_id: str) -> list[dict[str, Any]]:
        """Unlocks newer than the last ones handed out; advances the watermark.

        First call for a lock only sets the watermark and returns nothing.
        """
        unlocks = (self.data or {}).get(device_id, {}).get(DATA_UNLOCKS, [])
        newest = unlocks[0]["timestamp"] if unlocks else 0
        if device_id not in self.last_seen:
            self.last_seen[device_id] = newest
            return []
        fresh = [u for u in unlocks if u["timestamp"] > self.last_seen[device_id]]
        self.last_seen[device_id] = max(self.last_seen[device_id], newest)
        return list(reversed(fresh))

    # ------------------------------------------------------- call counting

    async def async_load_stats(self) -> None:
        stored = await self._store.async_load() or {}
        month = dt_util.now().strftime("%Y-%m")
        if stored.get("month") == month:
            self.calls_month = month
            self.calls = int(stored.get("calls", 0))
        else:
            self.calls_month = month
            self.calls = 0
        # The API counts from zero each time it is created; seed it with the
        # stored total so the sensor continues where it left off.
        self.api.calls = self.calls

    async def _async_save_stats(self) -> None:
        month = dt_util.now().strftime("%Y-%m")
        if month != self.calls_month:
            # New month: the allowance resets, and so does the counter.
            self.calls_month = month
            self.api.calls = 0
        self.calls = self.api.calls
        await self._store.async_save({"month": self.calls_month, "calls": self.calls})

    # -------------------------------------------------------------- repairs

    def _issue(self, issue_id: str, severity: ir.IssueSeverity, placeholders: dict[str, str]) -> None:
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=severity,
            translation_key=issue_id,
            translation_placeholders=placeholders,
            learn_more_url="https://platform.tuya.com/cloud/",
        )

    def _check_expiry_warning(self) -> None:
        """The owner can note the plan's end date; warn a month ahead."""
        raw = self.entry.options.get(CONF_SUBSCRIPTION_END)
        if not raw:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_SUBSCRIPTION_EXPIRING)
            return
        try:
            end = date.fromisoformat(str(raw))
        except ValueError:
            return
        days = (end - dt_util.now().date()).days
        if days <= EXPIRY_WARNING_DAYS:
            severity = ir.IssueSeverity.ERROR if days < 0 else ir.IssueSeverity.WARNING
            self._issue(ISSUE_SUBSCRIPTION_EXPIRING, severity, {"date": end.isoformat(), "days": str(max(days, 0))})
        else:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_SUBSCRIPTION_EXPIRING)

    # ----------------------------------------------------------------- push

    def start_push(self) -> None:
        if not self.entry.options.get(CONF_PUSH):
            self.push_status = "off"
            return
        host = PULSAR_HOSTS.get(self.entry.data[CONF_ENDPOINT])
        if host is None:
            _LOGGER.warning("No message queue host known for %s; push disabled", self.entry.data[CONF_ENDPOINT])
            self.push_status = "unsupported endpoint"
            return
        production = self.entry.options.get(CONF_PUSH_ENV, PUSH_ENV_PRODUCTION) == PUSH_ENV_PRODUCTION
        loop = self.hass.loop
        self.push = TuyaPushListener(
            host,
            self.entry.data[CONF_ACCESS_ID],
            self.entry.data[CONF_ACCESS_SECRET],
            production=production,
            on_message=lambda msg: loop.call_soon_threadsafe(self._handle_push, msg),
            on_status=lambda ok, why: loop.call_soon_threadsafe(self._handle_push_status, ok, why),
        )
        self.push_status = "connecting"
        self.push.start()

    def stop_push(self) -> None:
        if self.push is not None:
            self.push.stop()
            self.push = None
        self.push_connected = False
        self.push_status = "off"

    @callback
    def _handle_push_status(self, connected: bool, why: str) -> None:
        self.push_connected = connected
        self.push_status = "connected" if connected else (why or "disconnected")
        if connected:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_PUSH_UNAVAILABLE)
            _LOGGER.info("Push connection to Tuya's message service established")
        elif "500" in why:
            self._issue(ISSUE_PUSH_UNAVAILABLE, ir.IssueSeverity.WARNING, {"message": why})
        self.async_update_listeners()

    @callback
    def _handle_push(self, message: dict[str, Any]) -> None:
        device_id = message.get("devId") or message.get("bizData", {}).get("devId")
        # Everything goes on the bus, for anyone working out what their lock
        # sends. Only messages about configured locks do more than that.
        self.hass.bus.async_fire(BUS_EVENT_PUSH, {"device_id": device_id, "message": message})
        if device_id not in self.devices:
            return
        biz = message.get("bizCode")
        if biz in ("online", "offline"):
            self.devices[device_id].online = biz == "online"
            self.async_update_listeners()
            return
        refresh = False
        for item in message.get("status") or []:
            code = str(item.get("code") or "")
            value = item.get("value")
            if code == "doorbell":
                async_dispatcher_send(self.hass, f"{SIGNAL_RING}_{device_id}", value)
            elif code == "alarm_lock":
                async_dispatcher_send(self.hass, f"{SIGNAL_ALARM}_{device_id}", value)
            elif code.startswith("unlock_") or code in ("open_close", "door_opened", "lock_motor_state"):
                refresh = True
        if refresh:
            self._schedule_refresh(device_id)

    @callback
    def _schedule_refresh(self, device_id: str) -> None:
        """One refresh a few seconds after the last message about a lock."""
        if (cancel := self._pending_refresh.pop(device_id, None)) is not None:
            cancel()

        async def _go(_now: datetime) -> None:
            self._pending_refresh.pop(device_id, None)
            await self.async_refresh()

        self._pending_refresh[device_id] = async_call_later(self.hass, PUSH_REFRESH_DELAY, _go)
