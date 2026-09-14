"""Polls Tuya for every configured lock and holds the result.

One coordinator per config entry. Each refresh fetches, per lock, the temporary
codes, the recent unlock log and the members with their permanent methods. That
is roughly 3 + N calls per lock (N = members) against the Tuya project's
monthly allowance, so the interval is configurable and defaults to five
minutes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LOG_METHODS, TuyaAuthError, TuyaDevice, TuyaLockApi, TuyaLockError, temporary_slot
from .const import CONF_LOCKS, CONF_REFRESH_MINUTES, DATA_CODES, DATA_MEMBERS, DATA_UNLOCKS, DEFAULT_REFRESH_MINUTES, DOMAIN

_LOGGER = logging.getLogger(__name__)


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

    @property
    def lock_ids(self) -> list[str]:
        return list(self.entry.options.get(CONF_LOCKS, []))

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
            except TuyaLockError as err:
                # One lock failing must not blank the others; keep the last
                # known data for it and log why.
                _LOGGER.warning("Refresh failed for %s: %s", device_id, err)
                if self.data and device_id in self.data:
                    out[device_id] = self.data[device_id]
        return out

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            return await self.hass.async_add_executor_job(self._fetch_all)
        except TuyaAuthError as err:
            raise UpdateFailed(f"Tuya refused the credentials: {err}") from err
        except TuyaLockError as err:
            raise UpdateFailed(str(err)) from err

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
