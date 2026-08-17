"""WebSocket API for the HA Voice Hub administration panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get"})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    manager = hass.data[DOMAIN]
    connection.send_message(websocket_api.result_message(msg["id"], manager.public_data()))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/action", vol.Required("action"): str, vol.Optional("payload", default={}): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_action(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    manager = hass.data[DOMAIN]
    action = msg["action"]
    payload = msg.get("payload") or {}
    result: dict[str, Any] | None = None
    try:
        if action == "settings":
            await manager.async_update_settings(payload)
        elif action == "profiles":
            await manager.async_update_profiles(payload.get("profiles", {}))
        elif action == "zone_create":
            result = {"zone_id": await manager.async_create_zone(str(payload.get("name") or ""), str(payload.get("icon") or "mdi:speaker"), payload.get("volume"), bool(payload.get("include_in_all", True)))}
        elif action == "zone_update":
            await manager.async_update_zone(str(payload.get("zone_id") or ""), payload)
        elif action == "zone_delete":
            await manager.async_delete_zone(str(payload.get("zone_id") or ""))
        elif action == "speaker_add":
            await manager.async_add_speaker(str(payload.get("zone_id") or ""), str(payload.get("entity_id") or ""))
        elif action == "speaker_remove":
            await manager.async_remove_speaker(str(payload.get("zone_id") or ""), str(payload.get("entity_id") or ""))
        elif action == "rule_save":
            result = {"rule_id": await manager.async_save_rule(payload)}
        elif action == "rule_delete":
            await manager.async_delete_rule(str(payload.get("rule_id") or ""))
        elif action == "rule_toggle":
            await manager.async_toggle_rule(str(payload.get("rule_id") or ""), bool(payload.get("enabled", True)))
        elif action == "speak":
            speakers = payload.get("speakers")
            if isinstance(speakers, str):
                speakers = [speakers]
            result = await manager.async_speak(str(payload.get("message") or ""), zone=str(payload.get("zone") or "toute_maison"), profile=str(payload.get("profile") or "normal"), speakers=speakers, volume=payload.get("volume"), voice=payload.get("voice"), use_prefix=bool(payload.get("use_prefix", True)), tts_entity=payload.get("tts_entity"))
        elif action == "reload":
            await manager.async_reload()
        else:
            raise HomeAssistantError(f"Action inconnue: {action}")
        connection.send_message(websocket_api.result_message(msg["id"], {"result": result, "config": manager.public_data()}))
    except (HomeAssistantError, ValueError, TypeError) as err:
        connection.send_error(msg["id"], "voice_hub_error", str(err))


def async_register_websockets(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, websocket_get)
    websocket_api.async_register_command(hass, websocket_action)
