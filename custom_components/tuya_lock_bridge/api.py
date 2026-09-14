"""Tuya Smart Lock Open API client.

Everything in here is synchronous - tuya-connector-python is built on
`requests` - and must be called through the executor from Home Assistant.

Tuya locks deliberately offer no local API. Every operation goes through the
cloud, and the sensitive ones are guarded by a ticket system:

1. Ask for a ticket. The response carries a `ticket_key`, hex encoded, which
   is AES-256-ECB encrypted with the project's FULL Access Secret (32 chars,
   UTF-8) as the key. After PKCS7 unpadding it is a 16-character string.
2. That string is the AES-128-ECB key used to encrypt the PIN, PKCS7 padded.
   The hex output MUST be lowercase. Tuya's API accepts uppercase hex and
   answers `success: true`, but the lock then decodes it to a different PIN
   and the code simply never works. This cost people days on Tuya's forum.

Confirmed working on physical hardware: a Nivian NV-ACCESS-PIN-RFID-W WiFi
keypad, Tuya category `mk`. Other quirks are documented where they apply.
"""

from __future__ import annotations

import base64
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from tuya_connector import TuyaOpenAPI

_LOGGER = logging.getLogger(__name__)

# Categories Tuya uses for things that behave like a lock. `mk` is the WiFi
# access-control panel this was built against; the rest are door locks.
LOCK_CATEGORIES = {"mk", "ms", "jtmspro", "jtmsbh", "jtmsjh", "msp", "bxx"}

# Tuya's `phase` on a temporary password. Expiry is derived from the times,
# not from the phase: revoked and expired codes flip between 19 and 17.
PHASE_ACTIVE = 2
PHASE_PENDING_SYNC = 12
PHASE_REVOKED = 17

DP_TO_TYPE = {
    "unlock_password": "password",
    "unlock_card": "card",
    "unlock_fingerprint": "fingerprint",
    "unlock_face": "face",
}
TYPE_TO_DP = {v: k for k, v in DP_TO_TYPE.items()}

# Unlock methods as they appear in the unlock log (`status.code`).
LOG_METHODS = {
    "unlock_password_kit": "password",
    "unlock_card_kit": "card",
    "unlock_phone_remote_kit": "app",
    "unlock_temporary_kit": "temporary",
    "unlock_fingerprint_kit": "fingerprint",
    "unlock_key_kit": "key",
}


class TuyaLockError(Exception):
    """A Tuya API call did not succeed."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class TuyaAuthError(TuyaLockError):
    """Credentials were refused."""


class LockBusyError(TuyaLockError):
    """The lock is in enrolment mode and refuses other changes (code 2328).

    After a card enrolment is started the lock waits about a minute for a
    card; until then every other change on it is refused. Measured: the same
    call succeeds once the window has closed.
    """


def _aes_ecb_decrypt(key: bytes, data: bytes) -> bytes:
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(decryptor.update(data) + decryptor.finalize()) + unpadder.finalize()


def _aes_ecb_encrypt(key: bytes, data: bytes) -> bytes:
    padder = padding.PKCS7(128).padder()
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return encryptor.update(padder.update(data) + padder.finalize()) + encryptor.finalize()


def decrypt_ticket_key(ticket_key_hex: str, access_secret: str) -> str:
    return _aes_ecb_decrypt(access_secret.encode(), bytes.fromhex(ticket_key_hex)).decode()


def encrypt_password(password: str, ticket_key: str) -> str:
    # .hex() is lowercase. Keep it that way - see the module docstring.
    return _aes_ecb_encrypt(ticket_key.encode(), password.encode()).hex()


def parse_minutes(value: Any) -> int:
    """'11:00' or a number of minutes after midnight -> minutes."""
    if isinstance(value, bool):
        raise ValueError("invalid time of day")
    if isinstance(value, (int, float)):
        minutes = int(value)
    else:
        text = str(value).strip()
        if ":" in text:
            # 'HH:MM' from a form, 'HH:MM:SS' from a Home Assistant time selector
            parts = text.split(":")
            minutes = int(parts[0]) * 60 + int(parts[1])
        else:
            minutes = int(text)
    if not 0 <= minutes <= 1439:
        raise ValueError(f"time of day '{value}' falls outside 00:00-23:59")
    return minutes


def build_schedule(days: list[int], start: Any, end: Any) -> list[dict[str, Any]]:
    """A recurring daily pattern as Tuya's `schedule_list`.

    Weekdays are ISO: 1 = Monday .. 7 = Sunday. Tuya wants a bitmask where
    Sunday is bit 0 and Monday bit 1. Note that the API returns the mask with
    the bit order REVERSED (Sunday 128, Monday 64, ... Saturday 2), so the
    value you read back is not the number you sent. Measured by sending and
    re-reading: 2 -> 64, 8 -> 16, 127 -> 254.

    Only one block fits per code; two blocks return error 1109. `all_day` must
    stay false: with true Tuya silently drops the block and the code becomes
    valid around the clock. Express a full day as 00:00-23:59.
    """
    if not days:
        raise ValueError("pick at least one weekday")
    mask = 0
    for day in days:
        day = int(day)
        if not 1 <= day <= 7:
            raise ValueError(f"invalid weekday {day} - use 1 (Monday) to 7 (Sunday)")
        mask |= 1 << (day % 7)
    start_m, end_m = parse_minutes(start), parse_minutes(end)
    if end_m <= start_m:
        raise ValueError("the daily pattern ends before it starts")
    return [{"effective_time": start_m, "invalid_time": end_m, "working_day": mask, "all_day": False}]


def temporary_slot(value: Any) -> int | None:
    """For a temporary code the unlock log carries no name, only a six-byte
    base64 blob whose first four bytes are the slot number (`sn`): AAAAAQAA is
    1, AAAABQAA is 5. Resolving it against the code list gives the name."""
    try:
        raw = base64.b64decode(str(value))
        return int.from_bytes(raw[:4], "big") if len(raw) >= 4 else None
    except Exception:  # noqa: BLE001 - anything odd just means "unknown"
        return None


@dataclass
class TuyaDevice:
    device_id: str
    name: str
    category: str
    product_name: str
    online: bool

    @property
    def is_lock(self) -> bool:
        return self.category in LOCK_CATEGORIES


class TuyaLockApi:
    """Synchronous client. One instance per config entry; all calls serialised.

    Several Home Assistant tasks may call this concurrently (the coordinator,
    a service, a button press). TuyaOpenAPI keeps its access token in the
    object and refreshes it when it expires; two threads doing that at once
    produce errors that do not reproduce. Hence one lock around everything,
    re-entrant because an operation such as "get a ticket and use it" must be
    atomic.
    """

    def __init__(self, endpoint: str, access_id: str, access_secret: str) -> None:
        self._endpoint = endpoint
        self._access_id = access_id
        self._access_secret = access_secret
        self._api: TuyaOpenAPI | None = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ core

    def _client(self) -> TuyaOpenAPI:
        if self._api is None:
            api = TuyaOpenAPI(self._endpoint, self._access_id, self._access_secret)
            resp = api.connect()
            if not resp.get("success"):
                raise TuyaAuthError(resp.get("msg") or "authentication failed", resp.get("code"))
            self._api = api
        return self._api

    @staticmethod
    def _check(resp: dict[str, Any], what: str) -> dict[str, Any]:
        if resp.get("success"):
            return resp
        code = resp.get("code")
        msg = resp.get("msg") or str(resp)
        if code == 2328:
            raise LockBusyError(
                "the lock is still waiting for a card from an earlier enrolment - "
                "hold the card against the keypad, or try again in a minute",
                code,
            )
        if code in (1010, 1011, 1100, 1106, 28841105, 28841002):
            raise TuyaAuthError(f"could not {what}: {msg}", code)
        raise TuyaLockError(f"could not {what}: {msg}", code)

    def _get(self, path: str, params: dict | None = None, what: str = "read") -> Any:
        with self._lock:
            return self._check(self._client().get(path, params), what).get("result")

    def _post(self, path: str, body: dict | None = None, what: str = "write") -> Any:
        with self._lock:
            return self._check(self._client().post(path, body), what).get("result")

    def _put(self, path: str, body: dict | None = None, what: str = "update") -> Any:
        with self._lock:
            return self._check(self._client().put(path, body), what).get("result")

    def _delete(self, path: str, what: str = "delete") -> Any:
        with self._lock:
            return self._check(self._client().delete(path), what).get("result")

    def _ticket(self, device_id: str) -> tuple[str, str]:
        """(ticket_id, plain 16-char ticket key)."""
        result = self._post(f"/v1.0/smart-lock/devices/{device_id}/password-ticket", what="obtain a ticket")
        return result["ticket_id"], decrypt_ticket_key(result["ticket_key"], self._access_secret)

    # --------------------------------------------------------------- devices

    def test_connection(self) -> None:
        with self._lock:
            self._api = None
            self._client()

    def list_devices(self) -> list[TuyaDevice]:
        result = self._get("/v1.0/iot-01/associated-users/devices", {"size": 100}, "list devices")
        return [
            TuyaDevice(
                device_id=d.get("id", ""),
                name=d.get("name") or d.get("id", ""),
                category=d.get("category") or "",
                product_name=d.get("product_name") or "",
                online=bool(d.get("online")),
            )
            for d in (result or {}).get("devices", [])
        ]

    # ---------------------------------------------------------------- unlock

    def unlock(self, device_id: str) -> None:
        with self._lock:
            ticket_id, _ = self._ticket(device_id)
            self._post(
                f"/v1.1/devices/{device_id}/door-lock/password-free/open-door",
                {"ticket_id": ticket_id, "channel_id": 1},
                "open the door",
            )

    # ------------------------------------------------------- temporary codes

    def list_codes(self, device_id: str) -> list[dict[str, Any]]:
        return self._get(f"/v1.0/devices/{device_id}/door-lock/temp-passwords", what="fetch the code list") or []

    def create_code(
        self,
        device_id: str,
        password: str,
        name: str,
        effective_time: int,
        invalid_time: int,
        *,
        one_time: bool = False,
        schedule: list[dict[str, Any]] | None = None,
        time_zone: str | None = None,
    ) -> int:
        """Create a temporary code; returns its Tuya id.

        Tuya sometimes discards a freshly created code within minutes if the
        lock does not confirm it - especially two codes with the same name and
        window. Read the list back before trusting the id.
        """
        if not password.isdigit():
            raise ValueError("the PIN may only contain digits")
        if invalid_time <= effective_time:
            raise ValueError("the end date is not after the start date")
        with self._lock:
            ticket_id, key = self._ticket(device_id)
            body: dict[str, Any] = {
                "password": encrypt_password(password, key),
                "password_type": "ticket",
                "ticket_id": ticket_id,
                "effective_time": effective_time,
                "invalid_time": invalid_time,
                "name": name,
                # 0 = usable any number of times within the window, 1 = once.
                "type": 1 if one_time else 0,
            }
            if schedule:
                body["schedule_list"] = schedule
                body["time_zone"] = time_zone or "UTC"
            result = self._post(f"/v1.0/devices/{device_id}/door-lock/temp-password", body, "create the code")
        return int(result["id"])

    def revoke_code(self, device_id: str, code_id: int | str) -> None:
        """Revokes the password. The record stays in the list, phase flipping
        between 19 and 17; only purge_code removes it - that is what the bin
        icon in the Tuya app does."""
        self._delete(f"/v1.0/devices/{device_id}/door-lock/temp-passwords/{code_id}", "revoke the code")

    def purge_code(self, device_id: str, code_id: int | str) -> None:
        self._delete(f"/v1.0/devices/{device_id}/door-lock/temp-passwords/{code_id}/record", "purge the record")

    # ------------------------------------------------------------ unlock log

    def unlock_log(self, device_id: str, days: int = 7, count: int = 20) -> list[dict[str, Any]]:
        end = int(time.time() * 1000)
        start = end - days * 86400 * 1000
        result = self._get(
            f"/v1.1/devices/{device_id}/door-lock/open-logs",
            {"page_no": 1, "page_size": count, "start_time": start, "end_time": end},
            "fetch the unlock log",
        )
        return (result or {}).get("logs") or []

    # --------------------------------------------------------------- members

    @staticmethod
    def _is_home_user(user_type: Any) -> bool:
        """user_type from /v1.1/devices/{id}/users: 50 is an app account that
        shares the lock; lower values are profiles on the device itself."""
        try:
            return int(user_type) >= 50
        except (TypeError, ValueError):
            return False

    def _methods_of(self, device_id: str, user_id: str) -> list[dict[str, Any]]:
        result = self._get(
            f"/v1.0/smart-lock/devices/{device_id}/opmodes/{user_id}",
            {"page_no": 1, "page_size": 50},
            "fetch the unlock methods",
        )
        return (result.get("records") if isinstance(result, dict) else result) or []

    def list_members(self, device_id: str) -> list[dict[str, Any]]:
        """Every member with its permanent unlock methods and on/off state.

        Costs one call plus one or two per member.
        """
        result = self._get(f"/v1.1/devices/{device_id}/users", {"page_no": 1, "page_size": 100}, "fetch the members")
        users = (result.get("records") if isinstance(result, dict) else result) or []
        members = []
        for user in users:
            uid = user.get("user_id")
            home = self._is_home_user(user.get("user_type"))
            active = True
            if not home:
                detail = self._get(f"/v1.1/devices/{device_id}/users/{uid}", what="fetch a member") or {}
                active = detail.get("effective_flag", 1) == 1
            members.append(
                {
                    "user_id": uid,
                    "name": (user.get("nick_name") or "").strip(),
                    "home_user": home,
                    "active": active,
                    "methods": [
                        {
                            "sn": m.get("unlock_sn"),
                            "type": DP_TO_TYPE.get(m.get("dp_code"), m.get("dp_code")),
                            "name": (m.get("unlock_name") or "").strip(),
                            "phase": m.get("phase"),
                        }
                        for m in self._methods_of(device_id, uid)
                    ],
                }
            )
        return members

    def create_member(self, device_id: str, name: str) -> str:
        result = self._post(f"/v1.0/devices/{device_id}/user", {"nick_name": name, "sex": 0}, "create the profile")
        return result if isinstance(result, str) else (result.get("user_id") or result.get("id"))

    def delete_member(self, device_id: str, user_id: str) -> None:
        self._delete(f"/v1.0/devices/{device_id}/users/{user_id}", "delete the profile")

    def enrol_method(
        self, device_id: str, user_id: str, unlock_type: str, password: str | None = None, name: str | None = None
    ) -> int | None:
        """Add a permanent method to a profile. Returns the slot number for a
        PIN; None for a card or fingerprint, which the lock now waits for at
        the device - the card's identity cannot travel through the API.

        Only works for profiles on the device (user_type 2 in Tuya's path).
        Enrolling on an app account is refused with `param is illegal`.
        """
        if unlock_type not in TYPE_TO_DP:
            raise ValueError(f"unknown unlock type '{unlock_type}'")
        with self._lock:
            body: dict[str, Any] = {"unlock_type": unlock_type, "user_type": 2, "user_id": user_id}
            if unlock_type == "password":
                if not password or not password.isdigit():
                    raise ValueError("the PIN may only contain digits")
                ticket_id, key = self._ticket(device_id)
                body.update({"password_type": "ticket", "ticket_id": ticket_id, "password": encrypt_password(password, key)})
            before = {m.get("unlock_sn") for m in self._methods_of(device_id, user_id)}
            self._put(f"/v1.0/devices/{device_id}/door-lock/actions/entry", body, f"enrol the {unlock_type}")
            if unlock_type != "password":
                return None
            # Tuya names the method automatically ('11-8'); find the new slot
            # and rename it so the unlock log carries something readable.
            dp = TYPE_TO_DP[unlock_type]
            for _ in range(5):
                new = [m for m in self._methods_of(device_id, user_id) if m.get("dp_code") == dp and m.get("unlock_sn") not in before]
                if new:
                    sn = int(new[0]["unlock_sn"])
                    if name:
                        self.rename_method(device_id, unlock_type, sn, name)
                    return sn
                time.sleep(1)
        return None

    def rename_method(self, device_id: str, unlock_type: str, sn: int | str, name: str) -> None:
        self._put(
            f"/v1.0/devices/{device_id}/door-lock/opmodes/{sn}",
            {"dp_code": TYPE_TO_DP.get(unlock_type, unlock_type), "unlock_name": name},
            "rename the unlock method",
        )

    def delete_method(self, device_id: str, user_id: str, unlock_type: str, sn: int | str) -> None:
        self._delete(
            f"/v1.0/devices/{device_id}/door-lock/user-types/2/users/{user_id}/unlock-types/{unlock_type}/keys/{sn}",
            "delete the unlock method",
        )

    def set_member_active(self, device_id: str, user_id: str, active: bool) -> None:
        """Switch a profile off or on through its validity window. Off is a
        window in the past, on is permanent. The lock acknowledges with
        delivery_status SUCCESS. Everything the profile holds goes together.

        Tuya's freeze for individual temporary codes exists for Zigbee locks
        only; on the keypad this was built against it answers 2004
        'not support the lock type'.
        """
        if active:
            schedule: dict[str, Any] = {"permanent": True}
        else:
            now = int(time.time())
            schedule = {"permanent": False, "effective_time": now - 7200, "expired_time": now - 3600}
        self._put(
            f"/v1.0/smart-lock/devices/{device_id}/users/{user_id}/schedule",
            {"schedule": schedule},
            "enable the profile" if active else "disable the profile",
        )
