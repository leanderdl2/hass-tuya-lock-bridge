"""Constants for Tuya Lock Bridge."""

DOMAIN = "tuya_lock_bridge"

CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_ENDPOINT = "endpoint"
CONF_LOCKS = "locks"
CONF_REFRESH_MINUTES = "refresh_minutes"

DEFAULT_REFRESH_MINUTES = 5

ENDPOINTS = {
    "https://openapi.tuyaeu.com": "Central Europe",
    "https://openapi-weaz.tuyaeu.com": "Western Europe",
    "https://openapi.tuyaus.com": "Western America",
    "https://openapi-ueaz.tuyaus.com": "Eastern America",
    "https://openapi.tuyacn.com": "China",
    "https://openapi.tuyain.com": "India",
}

PLATFORMS = ["button", "sensor", "event", "switch"]

# Coordinator data keys, per device id
DATA_CODES = "codes"
DATA_UNLOCKS = "unlocks"
DATA_MEMBERS = "members"

EVENT_TYPE_UNLOCK = "unlock"
