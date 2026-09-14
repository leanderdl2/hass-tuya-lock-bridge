# Tuya Lock Bridge

[![HACS custom repository](https://img.shields.io/badge/HACS-custom%20repository-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)

A Home Assistant integration for Tuya smart locks and access-control keypads:
open the door, manage temporary access codes, keep profiles with permanent PINs
and cards, and see who opened the door — as native entities and services.

Home Assistant's own Tuya integration supports every platform *except* `lock`
and `remote`, so a Tuya keypad shows up there as a read-only binary sensor with
no way to control it. This integration fills that gap through Tuya's Smart Lock
Open APIs.

## What you get

Per lock, one device with:

| Entity | Does |
|---|---|
| `button.<lock>_open` | Opens the door |
| `sensor.<lock>_valid_codes` | Temporary codes valid right now; the full list in its attributes |
| `sensor.<lock>_last_unlock` | Who opened the door last, how, and when; the twenty before it in `recent` |
| `event.<lock>_unlock` | Fires once per unlock — trigger an automation on who came in |
| `switch.<lock>_profile_<name>` | One per profile: off means its codes and cards stop opening the door |

A **Locks** page in the sidebar (administrators only) to do all of this by
hand: see the codes on a lock, create one, revoke it, open the door, manage
profiles and their PINs and cards. It is a custom panel that talks to Home
Assistant over its own connection — no port, no token.

And services (actions) for everything the entities cannot express:
`tuya_lock_bridge.book`, `create_code`, `revoke_code`, `purge_code`,
`list_codes`, `add_profile`, `delete_profile`, `add_method`, `rename_method`,
`delete_method`, `list_profiles`, `unlock`, `refresh`. The ones that create
something answer with its id, so an automation can keep it for later.

Entity names follow your Home Assistant language; Dutch and English are
included.

## Installation

Until this is in the HACS default store, add it as a custom repository:

1. HACS → three dots → *Custom repositories*
2. Repository `https://github.com/leanderdl2/hass-tuya-lock-bridge`, type *Integration*
3. Install **Tuya Lock Bridge**, restart Home Assistant
4. Settings → Devices & services → *Add integration* → Tuya Lock Bridge

Or copy `custom_components/tuya_lock_bridge` into your `config/custom_components`
and restart.

## Setting it up

You need a Cloud Development project on [iot.tuya.com](https://iot.tuya.com)
with your Tuya / Smart Life app account linked, subscribed to the **Smart Lock
Open Service**. The integration asks for the project's Access ID, Access Secret
and data centre, then lists your devices and pre-selects the locks.

Mind the project's subscription. The Trial Edition comes with a monthly
allowance and has to be extended periodically; when it lapses every API call
stops, and so does this integration. Each refresh costs a handful of calls per
lock; the interval is five minutes by default and can be changed under the
integration's options.

## A code per booking

The pattern this was built for: a guesthouse where every booking gets its own
code from the calendar, gone again at checkout.

```yaml
- action: tuya_lock_bridge.book
  data:
    device_id: !input lock
    last4: "{{ phone[-4:] }}"
    checkin: "{{ checkin }}"
    checkout: "{{ checkout }}"
  response_variable: booking
- action: notify.send_message
  data:
    message: "Code {{ booking.name }} created (id {{ booking.code_id }})"
```

The PIN is the two-digit year of check-in plus the last four digits of the
guest's phone number: a check-in in 2026 with phone …4321 gives `264321`. Six
digits, which is what most keypads expect.

## Profiles

A profile is a member of the lock with permanent unlock methods. `add_profile`
creates one with a PIN; `add_method` adds another PIN — or starts card
enrolment, after which you hold the card against the keypad within a minute.
The card's identity cannot travel through the API, which is why that step
happens at the device.

Each profile gets a switch. Off means everything the profile holds stops
opening the door, on brings it back; nothing is deleted. Handy for "the cleaner
only on changeover days".

App accounts that share the lock are listed with their methods but left alone —
manage those in the Tuya app.

## Which locks

Developed against a Nivian NV-ACCESS-PIN-RFID-W WiFi keypad (Tuya category
`mk`), where unlocking, code management and profiles are confirmed on physical
hardware. It should work with any Tuya lock that exposes the Smart Lock Open
Service APIs; reports about other models are welcome.

**Recurring daily patterns are the exception.** Tuya's documentation states
they are supported only by Zigbee residential lock pro and hotel lock. The
cloud accepts and stores a pattern for other locks, but whether your lock
enforces the hours is untested — if it does not, a code meant for "every day
11:00 to 15:00" works around the clock within its outer window. Try one outside
its hours before relying on it.

If all you want is opening and closing, look at
[Xtend Tuya](https://github.com/azerty9971/xtend_tuya) first: a community
integration that adds `lock` entities for some devices. It does not manage
access codes, and on the keypad above its lock entities did not open the door.

## Relation to the add-on

This integration replaces the [Tuya Lock Bridge add-on](https://github.com/leanderdl2/tuya-lock-bridge),
which did the same over an HTTP API and MQTT and needed Home Assistant OS. The
integration works on every install type, needs no port and no MQTT, and answers
service calls directly. The add-on stays available for anyone already using it.

The Tuya quirks that made the add-on possible — why the encrypted PIN must be
lowercase hex, why revoking a code does not remove it from the list, why
`all_day: true` does the opposite of what it says — are documented in
[`api.py`](custom_components/tuya_lock_bridge/api.py) where they apply.

## Licence

MIT — see [LICENSE](LICENSE).
