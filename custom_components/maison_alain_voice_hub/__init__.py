"""HA Voice Hub integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PROFILE_NAMES, SERVICE_RELOAD, SERVICE_SPEAK
from .manager import VoiceHubManager
from .panel import async_register_panel, async_unregister_panel
from .websocket import async_register_websockets

_LOGGER = logging.getLogger(__name__)

SPEAK_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Optional("zone", default="toute_maison"): cv.string,
        vol.Optional("profile", default="normal"): vol.In(PROFILE_NAMES),
        vol.Optional("speakers"): vol.Any(cv.entity_id, [cv.entity_id]),
        vol.Optional("volume"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        vol.Optional("voice"): cv.string,
        vol.Optional("use_prefix", default=True): cv.boolean,
        vol.Optional("tts_entity"): cv.entity_id,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Voice Hub manager, services and admin panel."""
    manager = VoiceHubManager(hass)
    await manager.async_load()
    hass.data[DOMAIN] = manager

    async def handle_speak(call: ServiceCall) -> None:
        speakers = call.data.get("speakers")
        if isinstance(speakers, str):
            speakers = [speakers]
        await manager.async_speak(
            call.data["message"],
            zone=call.data.get("zone"),
            profile=call.data.get("profile", "normal"),
            speakers=speakers,
            volume=call.data.get("volume"),
            voice=call.data.get("voice"),
            use_prefix=call.data.get("use_prefix", True),
            tts_entity=call.data.get("tts_entity"),
        )

    async def handle_reload(call: ServiceCall) -> None:
        await manager.async_reload()

    hass.services.async_register(DOMAIN, SERVICE_SPEAK, handle_speak, schema=SPEAK_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RELOAD, handle_reload)

    await async_register_panel(hass)
    async_register_websockets(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Apply initial values selected in the UI config flow."""
    manager: VoiceHubManager = hass.data[DOMAIN]
    await manager.async_apply_setup_defaults(
        tts_entity=entry.data.get("tts_entity"),
        default_speaker=entry.data.get("default_speaker"),
        prefix=entry.data.get("prefix"),
        voice=entry.data.get("voice"),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry without destroying stored Voice Hub data."""
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the sidebar panel when the integration entry is deleted."""
    async_unregister_panel(hass)
