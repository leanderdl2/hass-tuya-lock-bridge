"""Real-time messages from Tuya's Message Service (Pulsar over WebSocket).

Polling tells you who opened the door within one refresh interval. This
listener hears it within seconds, and it is the only way to get a doorbell
press or a wrong-PIN alarm at all: those never appear in the unlock log.

The protocol, taken from tuya-connector-python's TuyaOpenPulsar and checked
against a live connection:

- URL: <queue host>ws/v2/consumer/persistent/<access_id>/out/<topic>/<access_id>-sub
  where topic is `event` (production) or `event-test`. Which one works is
  decided by the "environment" of the Message Service in the Tuya console; the
  other answers the handshake with HTTP 500.
- Headers: username = access_id, password = md5(access_id + md5(secret))[8:24].
- Each frame is JSON with `messageId`, a base64 `payload` and `properties`;
  the payload is JSON whose `data` is base64 of the message encrypted with
  secret[8:24] as the key. Two schemes exist, chosen per project in the
  console: AES-128-ECB with PKCS7 padding (the original, `em: aes_ecb`) and
  AES-128-GCM with a 12-byte nonce in front and the 16-byte tag at the end
  (`em: aes_gcm`, what new projects get). The property says which; when it is
  missing both are tried.
  Every frame must be acknowledged with {"messageId": ...} or it is redelivered.
- Decrypted, a status report looks like
  {"devId": "...", "status": [{"code": "unlock_password", "value": 1, "t": 169...}]}
  and a lifecycle message like {"bizCode": "online", "devId": "..."}.

Runs in its own thread (websocket-client is blocking) and hands every decoded
message to the event loop. Messages cost Message Service credits, so the
listener is opt-in.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import ssl
import threading
import time
from collections.abc import Callable
from typing import Any

import websocket
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_LOGGER = logging.getLogger(__name__)

QUERY = "?ackTimeoutMillis=3000&subscriptionType=Failover"
PING_INTERVAL = 30
PING_TIMEOUT = 10
RECONNECT_MIN = 5
RECONNECT_MAX = 300


def _pulsar_password(access_id: str, access_secret: str) -> str:
    inner = hashlib.md5(access_secret.encode()).hexdigest()
    return hashlib.md5((access_id + inner).encode()).hexdigest()[8:24]


def _decrypt_ecb(blob: bytes, key: bytes) -> bytes:
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    raw = decryptor.update(blob) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(raw) + unpadder.finalize()


def _decrypt_gcm(blob: bytes, key: bytes) -> bytes:
    if len(blob) < 12 + 16:
        raise ValueError("too short for AES-GCM")
    return AESGCM(key).decrypt(blob[:12], blob[12:], None)


def decrypt_message(data_b64: str, access_secret: str, model: str | None = None) -> dict[str, Any]:
    """`model` is the frame's `em` property: aes_ecb, aes_gcm, or unknown."""
    key = access_secret[8:24].encode()
    blob = base64.b64decode(data_b64)
    order = [_decrypt_gcm, _decrypt_ecb] if model == "aes_gcm" else [_decrypt_ecb, _decrypt_gcm]
    last: Exception | None = None
    for fn in order:
        try:
            return json.loads(fn(blob, key))
        except (InvalidTag, ValueError, UnicodeDecodeError, json.JSONDecodeError) as err:
            last = err
    raise ValueError(f"could not decrypt push message: {last}")


class PushUnavailable(Exception):
    """The queue refused the handshake - most likely the wrong environment."""


class TuyaPushListener(threading.Thread):
    """One connection per config entry.

    `on_message(dict)` and `on_status(bool, str)` are called from this thread;
    the caller is responsible for hopping to the event loop.
    """

    def __init__(
        self,
        host: str,
        access_id: str,
        access_secret: str,
        *,
        production: bool,
        on_message: Callable[[dict[str, Any]], None],
        on_status: Callable[[bool, str], None],
    ) -> None:
        super().__init__(name="tuya_lock_bridge-push", daemon=True)
        topic = "event" if production else "event-test"
        self._url = f"{host}ws/v2/consumer/persistent/{access_id}/out/{topic}/{access_id}-sub{QUERY}"
        self._headers = {"Connection": "Upgrade", "username": access_id, "password": _pulsar_password(access_id, access_secret)}
        self._secret = access_secret
        self._on_message = on_message
        self._on_status = on_status
        self._stop = threading.Event()
        self._app: websocket.WebSocketApp | None = None
        self.connected = False
        self.last_error = ""

    # ----------------------------------------------------------- callbacks

    def _handle_open(self, _app: websocket.WebSocketApp) -> None:
        self.connected = True
        self.last_error = ""
        self._on_status(True, "")

    def _handle_message(self, app: websocket.WebSocketApp, frame: str) -> None:
        try:
            envelope = json.loads(frame)
            payload = json.loads(base64.b64decode(envelope["payload"]))
            model = (envelope.get("properties") or {}).get("em")
            message = decrypt_message(payload["data"], self._secret, model)
        except Exception as err:  # noqa: BLE001 - a bad frame must not kill the thread
            _LOGGER.debug("Undecodable push frame: %s (%s)", frame[:200], err)
            message = None
        # Acknowledge whatever arrived, decodable or not; otherwise Tuya
        # redelivers it every few seconds and burns credits.
        try:
            app.send(json.dumps({"messageId": envelope["messageId"]}))
        except Exception:  # noqa: BLE001
            pass
        if message is not None:
            self._on_message(message)

    def _handle_error(self, _app: websocket.WebSocketApp, err: Exception) -> None:
        self.last_error = str(err)
        _LOGGER.debug("Push connection error: %s", err)

    def _handle_close(self, _app: websocket.WebSocketApp, code: Any, msg: Any) -> None:
        if self.connected:
            self.connected = False
            self._on_status(False, f"closed ({code} {msg})")

    # ---------------------------------------------------------------- loop

    def run(self) -> None:
        delay = RECONNECT_MIN
        while not self._stop.is_set():
            self._app = websocket.WebSocketApp(
                self._url,
                header=self._headers,
                on_open=self._handle_open,
                on_message=self._handle_message,
                on_error=self._handle_error,
                on_close=self._handle_close,
            )
            started = time.monotonic()
            try:
                self._app.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}, ping_interval=PING_INTERVAL, ping_timeout=PING_TIMEOUT)
            except Exception as err:  # noqa: BLE001
                self.last_error = str(err)
            if self._stop.is_set():
                break
            if "500" in self.last_error:
                # A 500 on the handshake is not transient: the topic does not
                # exist for this project. Tell the owner once, then keep
                # trying slowly in case they fix the console setting.
                self._on_status(False, "handshake refused (HTTP 500) - check the Message Service environment in the Tuya console")
                delay = RECONNECT_MAX
            elif time.monotonic() - started > 60:
                delay = RECONNECT_MIN  # it ran for a while; a quick retry is fine
            else:
                delay = min(delay * 2, RECONNECT_MAX)
            self._stop.wait(delay)

    def stop(self) -> None:
        self._stop.set()
        if self._app is not None:
            try:
                self._app.close()
            except Exception:  # noqa: BLE001
                pass
