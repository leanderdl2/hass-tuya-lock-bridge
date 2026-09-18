"""Describe the audit events in Home Assistant's logbook: who did what."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.core import Event, HomeAssistant, callback

from .const import BUS_EVENT_ACTION, DOMAIN

MESSAGES = {
    "en": {
        "unlock": "{user} opened the door",
        "create_code": "{user} created code {name}",
        "revoke_code": "{user} revoked code {name}",
        "purge_code": "{user} removed code {name} from the list",
        "add_profile": "{user} added profile {name}",
        "delete_profile": "{user} deleted profile {name}",
        "add_method": "{user} added a {type} to profile {name}",
        "rename_method": "{user} renamed a {type} to {name}",
        "delete_method": "{user} removed a {type} from profile {name}",
        "enable_profile": "{user} enabled profile {name}",
        "disable_profile": "{user} disabled profile {name}",
    },
    "nl": {
        "unlock": "{user} heeft de deur geopend",
        "create_code": "{user} heeft code {name} aangemaakt",
        "revoke_code": "{user} heeft code {name} ingetrokken",
        "purge_code": "{user} heeft code {name} uit de lijst verwijderd",
        "add_profile": "{user} heeft profiel {name} toegevoegd",
        "delete_profile": "{user} heeft profiel {name} verwijderd",
        "add_method": "{user} heeft een {type} toegevoegd aan profiel {name}",
        "rename_method": "{user} heeft een {type} hernoemd naar {name}",
        "delete_method": "{user} heeft een {type} verwijderd van profiel {name}",
        "enable_profile": "{user} heeft profiel {name} ingeschakeld",
        "disable_profile": "{user} heeft profiel {name} uitgeschakeld",
    },
}
TYPES = {"en": {"password": "PIN", "card": "card"}, "nl": {"password": "pincode", "card": "pasje"}}


@callback
def async_describe_events(hass: HomeAssistant, async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None]) -> None:
    lang = "nl" if (hass.config.language or "").startswith("nl") else "en"
    texts, types = MESSAGES[lang], TYPES[lang]

    @callback
    def describe(event: Event) -> dict[str, str]:
        d = dict(event.data)
        d["type"] = types.get(d.get("type", ""), d.get("type", ""))
        template = texts.get(d.get("action", ""), "{user}: {action}")
        try:
            message = template.format(**{k: d.get(k, "?") for k in ("user", "name", "type", "action")})
        except (KeyError, IndexError):
            message = f"{d.get('user')}: {d.get('action')}"
        return {LOGBOOK_ENTRY_NAME: d.get("lock", "Tuya Lock Bridge"), LOGBOOK_ENTRY_MESSAGE: message}

    async_describe_event(DOMAIN, BUS_EVENT_ACTION, describe)
