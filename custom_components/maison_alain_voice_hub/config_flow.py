"""Config flow for HA Voice Hub."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import DEFAULT_PREFIX, DEFAULT_VOICE, DOMAIN


class MaisonAlainVoiceHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Voice Hub setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Create the single Voice Hub config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="HA Voice Hub", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("tts_entity"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="tts")
                    ),
                    vol.Required("default_speaker"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="media_player")
                    ),
                    vol.Optional("prefix", default=DEFAULT_PREFIX): str,
                    vol.Optional("voice", default=DEFAULT_VOICE): str,
                }
            ),
        )
