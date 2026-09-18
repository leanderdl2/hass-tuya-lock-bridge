"""Constants for Tuya Lock Bridge."""

DOMAIN = "tuya_lock_bridge"
VERSION = "0.4.2"

CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_ENDPOINT = "endpoint"
CONF_LOCKS = "locks"
CONF_REFRESH_MINUTES = "refresh_minutes"
CONF_PUSH = "push"
CONF_PUSH_ENV = "push_env"
CONF_SUBSCRIPTION_END = "subscription_end"

PUSH_ENV_PRODUCTION = "production"
PUSH_ENV_TEST = "test"

DEFAULT_REFRESH_MINUTES = 5

ENDPOINTS = {
    "https://openapi.tuyaeu.com": "Central Europe",
    "https://openapi-weaz.tuyaeu.com": "Western Europe",
    "https://openapi.tuyaus.com": "Western America",
    "https://openapi-ueaz.tuyaus.com": "Eastern America",
    "https://openapi.tuyacn.com": "China",
    "https://openapi.tuyain.com": "India",
}

# Tuya's message queue (Pulsar over WebSocket) lives on a different host than
# the REST API. The regional variants (-weaz, -ueaz) share their region's
# queue host; measured for Central Europe only.
PULSAR_HOSTS = {
    "https://openapi.tuyaeu.com": "wss://mqe.tuyaeu.com:8285/",
    "https://openapi-weaz.tuyaeu.com": "wss://mqe.tuyaeu.com:8285/",
    "https://openapi.tuyaus.com": "wss://mqe.tuyaus.com:8285/",
    "https://openapi-ueaz.tuyaus.com": "wss://mqe.tuyaus.com:8285/",
    "https://openapi.tuyacn.com": "wss://mqe.tuyacn.com:8285/",
    "https://openapi.tuyain.com": "wss://mqe.tuyain.com:8285/",
}

PLATFORMS = ["button", "event", "lock", "sensor", "switch"]

# Coordinator data keys, per device id
DATA_CODES = "codes"
DATA_UNLOCKS = "unlocks"
DATA_MEMBERS = "members"

EVENT_TYPE_UNLOCK = "unlock"
EVENT_TYPE_RING = "ring"
# Alarm reasons as the event entity reports them; anything Tuya sends that is
# not in this list becomes "other" with the raw value in the attributes.
ALARM_TYPES = ["wrong_password", "wrong_card", "wrong_fingerprint", "wrong_face", "tamper", "hijack", "lock_stuck", "low_battery", "other"]

# Fired on the Home Assistant bus for every decoded push message, so anyone can
# see what a lock actually sends without enabling debug logging.
BUS_EVENT_PUSH = f"{DOMAIN}_push"
# Fired for every change made through this integration, with the Home
# Assistant user that made it; described in the logbook by logbook.py.
BUS_EVENT_ACTION = f"{DOMAIN}_action"

# Repair issue ids
ISSUE_SUBSCRIPTION_EXPIRED = "subscription_expired"
ISSUE_SUBSCRIPTION_EXPIRING = "subscription_expiring"
ISSUE_API_NOT_AUTHORISED = "api_not_authorised"
ISSUE_PUSH_UNAVAILABLE = "push_unavailable"
