"""Core manager for HA Voice Hub."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import logging
import time
from typing import Any
from uuid import uuid4

from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.template import Template
from homeassistant.util import slugify

from .const import (
    DEFAULT_PREFIX,
    DEFAULT_PROFILES,
    DEFAULT_RULES,
    DEFAULT_SPEAKER,
    DEFAULT_TTS_ENTITY,
    DEFAULT_ZONES,
    DOMAIN,
    PROFILE_NAMES,
    STORAGE_KEY,
    STORAGE_VERSION,
    STARTUP_GRACE_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


def _default_data() -> dict[str, Any]:
    return {
        "enabled": True,
        "tts_entity": DEFAULT_TTS_ENTITY,
        "default_speaker": DEFAULT_SPEAKER,
        "prefix": DEFAULT_PREFIX,
        "cache": True,
        "fallback_to_default": True,
        "restore_volume": True,
        "profiles": deepcopy(DEFAULT_PROFILES),
        "zones": deepcopy(DEFAULT_ZONES),
        "rules": deepcopy(DEFAULT_RULES),
    }


class VoiceHubManager:
    """Store, route and execute HA Voice Hub announcements."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = _default_data()
        self.last_announcement: dict[str, Any] | None = None
        self._listener_unsub = None
        self._pending: dict[str, asyncio.Task] = {}
        self._last_fired: dict[str, float] = {}
        self._save_lock = asyncio.Lock()
        self._speak_lock = asyncio.Lock()
        self._started_monotonic = time.monotonic()

    async def async_load(self) -> None:
        """Load configuration from Home Assistant supported storage."""
        stored = await self._store.async_load()
        if stored is None:
            self.data = _default_data()
            await self.async_save()
        else:
            defaults = _default_data()
            defaults.update(stored)
            defaults.setdefault("profiles", deepcopy(DEFAULT_PROFILES))
            defaults.setdefault("zones", deepcopy(DEFAULT_ZONES))
            defaults.setdefault("rules", deepcopy(DEFAULT_RULES))
            for name, profile in DEFAULT_PROFILES.items():
                defaults["profiles"].setdefault(name, deepcopy(profile))
                for key, value in profile.items():
                    defaults["profiles"][name].setdefault(key, value)
            for zone_id, zone_data in defaults.get("zones", {}).items():
                zone_data.setdefault("include_in_all", zone_id != "portable")
                zone_data.setdefault("speakers", [])
                zone_data.setdefault("volume", None)
            self.data = defaults
        await self.async_rebuild_rule_listener()

    async def async_save(self) -> None:
        """Persist configuration."""
        async with self._save_lock:
            await self._store.async_save(self.data)

    async def async_reload(self) -> None:
        """Reload configuration and rules from disk."""
        for task in list(self._pending.values()):
            task.cancel()
        self._pending.clear()
        await self.async_load()

    async def async_shutdown(self) -> None:
        """Stop listeners and pending delayed rules."""
        if self._listener_unsub is not None:
            self._listener_unsub()
            self._listener_unsub = None
        for task in list(self._pending.values()):
            task.cancel()
        self._pending.clear()

    def public_data(self) -> dict[str, Any]:
        """Return configuration safe for the administration panel."""
        result = deepcopy(self.data)
        result["last_announcement"] = deepcopy(self.last_announcement)
        result["virtual_zones"] = {
            "toute_maison": {
                "name": "Toute la maison",
                "icon": "mdi:home-sound-in",
                "speakers": self.resolve_speakers("toute_maison"),
            }
        }
        return result

    async def async_apply_setup_defaults(self, *, tts_entity: str | None = None, default_speaker: str | None = None, prefix: str | None = None, voice: str | None = None) -> None:
        changed = False
        if tts_entity:
            self.data["tts_entity"] = tts_entity
            changed = True
        if default_speaker:
            self.data["default_speaker"] = default_speaker
            portable = self.data.setdefault("zones", {}).setdefault("portable", {"name": "Portable", "icon": "mdi:laptop", "speakers": [], "volume": None, "include_in_all": False})
            if default_speaker not in portable.setdefault("speakers", []):
                portable["speakers"].append(default_speaker)
            changed = True
        if prefix is not None:
            self.data["prefix"] = prefix
            changed = True
        if voice:
            for profile_name in PROFILE_NAMES:
                self.data["profiles"].setdefault(profile_name, {})["voice"] = voice
            changed = True
        if changed:
            await self.async_save()

    async def async_update_settings(self, values: dict[str, Any]) -> None:
        allowed = {"enabled", "tts_entity", "default_speaker", "prefix", "cache", "fallback_to_default", "restore_volume"}
        for key in allowed:
            if key in values:
                self.data[key] = values[key]
        await self.async_save()

    async def async_update_profiles(self, profiles: dict[str, Any]) -> None:
        for name in PROFILE_NAMES:
            if name not in profiles:
                continue
            current = self.data.setdefault("profiles", {}).setdefault(name, {})
            incoming = profiles[name]
            if "volume" in incoming:
                current["volume"] = max(0.0, min(1.0, float(incoming["volume"])))
            if "voice" in incoming:
                current["voice"] = str(incoming["voice"]).strip()
            if "tts_entity" in incoming:
                candidate_tts = str(incoming["tts_entity"] or "").strip()
                if not candidate_tts or candidate_tts.startswith("tts."):
                    current["tts_entity"] = candidate_tts
            if "style" in incoming:
                current["style"] = str(incoming["style"]).strip()
        await self.async_save()

    async def async_create_zone(self, name: str, icon: str = "mdi:speaker", volume: Any = None, include_in_all: bool = True) -> str:
        zone_id = slugify(name)
        if not zone_id or zone_id == "toute_maison":
            raise HomeAssistantError("Nom de zone invalide ou reserve")
        zones = self.data.setdefault("zones", {})
        if zone_id in zones:
            raise HomeAssistantError("Cette zone existe deja")
        zone_volume = None if volume in (None, "") else max(0.0, min(1.0, float(volume)))
        zones[zone_id] = {"name": name.strip(), "icon": icon.strip() or "mdi:speaker", "speakers": [], "volume": zone_volume, "include_in_all": bool(include_in_all)}
        await self.async_save()
        return zone_id

    async def async_update_zone(self, zone_id: str, values: dict[str, Any]) -> None:
        zone = self.data.setdefault("zones", {}).get(zone_id)
        if zone is None:
            raise HomeAssistantError("Zone inconnue")
        if "name" in values and str(values["name"]).strip():
            zone["name"] = str(values["name"]).strip()
        if "icon" in values:
            zone["icon"] = str(values["icon"]).strip() or "mdi:speaker"
        if "volume" in values:
            raw = values["volume"]
            zone["volume"] = None if raw in (None, "") else max(0.0, min(1.0, float(raw)))
        if "include_in_all" in values:
            zone["include_in_all"] = bool(values["include_in_all"])
        await self.async_save()

    async def async_delete_zone(self, zone_id: str) -> None:
        if zone_id == "portable":
            raise HomeAssistantError("La zone portable de secours ne peut pas etre supprimee")
        zones = self.data.setdefault("zones", {})
        if zone_id not in zones:
            raise HomeAssistantError("Zone inconnue")
        zones.pop(zone_id)
        for rule in self.data.setdefault("rules", []):
            if rule.get("zone") == zone_id:
                rule["zone"] = "toute_maison"
        await self.async_save()

    async def async_add_speaker(self, zone_id: str, entity_id: str) -> None:
        if not entity_id.startswith("media_player."):
            raise HomeAssistantError("L entite doit etre un media_player")
        zone = self.data.setdefault("zones", {}).get(zone_id)
        if zone is None:
            raise HomeAssistantError("Zone inconnue")
        speakers = zone.setdefault("speakers", [])
        if entity_id not in speakers:
            speakers.append(entity_id)
            await self.async_save()

    async def async_remove_speaker(self, zone_id: str, entity_id: str) -> None:
        zone = self.data.setdefault("zones", {}).get(zone_id)
        if zone is None:
            raise HomeAssistantError("Zone inconnue")
        speakers = zone.setdefault("speakers", [])
        if entity_id in speakers:
            speakers.remove(entity_id)
            await self.async_save()

    async def async_save_rule(self, rule: dict[str, Any]) -> str:
        rule_id = str(rule.get("id") or f"rule_{uuid4().hex[:10]}")
        normalized = {
            "id": rule_id,
            "name": str(rule.get("name") or rule_id).strip(),
            "entity_id": str(rule.get("entity_id") or "").strip(),
            "trigger": str(rule.get("trigger") or "state").strip(),
            "value": str(rule.get("value") if rule.get("value") is not None else "").strip(),
            "message": str(rule.get("message") or "").strip(),
            "zone": str(rule.get("zone") or "toute_maison").strip(),
            "profile": str(rule.get("profile") or "normal").strip(),
            "for_seconds": max(0, int(float(rule.get("for_seconds") or 0))),
            "cooldown": max(0, int(float(rule.get("cooldown") or 0))),
            "enabled": bool(rule.get("enabled", True)),
            "condition_entity": str(rule.get("condition_entity") or "").strip(),
            "condition_operator": str(rule.get("condition_operator") or "").strip(),
            "condition_value": str(rule.get("condition_value") if rule.get("condition_value") is not None else "").strip(),
        }
        if "." not in normalized["entity_id"]:
            raise HomeAssistantError("Entite invalide")
        if not normalized["message"]:
            raise HomeAssistantError("Le message ne peut pas etre vide")
        if normalized["trigger"] not in {"state", "above", "below", "changed", "available", "unavailable"}:
            raise HomeAssistantError("Type de declencheur invalide")
        if normalized["condition_operator"] not in {"", "state", "not_state", "above", "below", "in", "not_in", "available", "unavailable"}:
            raise HomeAssistantError("Operateur de condition invalide")
        if normalized["condition_entity"] and "." not in normalized["condition_entity"]:
            raise HomeAssistantError("Entite de condition invalide")
        if normalized["profile"] not in PROFILE_NAMES:
            normalized["profile"] = "normal"
        if normalized["zone"] != "toute_maison" and normalized["zone"] not in self.data.get("zones", {}):
            normalized["zone"] = "toute_maison"
        rules = self.data.setdefault("rules", [])
        for index, existing in enumerate(rules):
            if existing.get("id") == rule_id:
                rules[index] = normalized
                break
        else:
            rules.append(normalized)
        await self.async_save()
        await self.async_rebuild_rule_listener()
        return rule_id

    async def async_delete_rule(self, rule_id: str) -> None:
        self.data["rules"] = [rule for rule in self.data.get("rules", []) if rule.get("id") != rule_id]
        task = self._pending.pop(rule_id, None)
        if task:
            task.cancel()
        await self.async_save()
        await self.async_rebuild_rule_listener()

    async def async_toggle_rule(self, rule_id: str, enabled: bool) -> None:
        for rule in self.data.get("rules", []):
            if rule.get("id") == rule_id:
                rule["enabled"] = enabled
                break
        await self.async_save()
        await self.async_rebuild_rule_listener()

    def resolve_speakers(self, zone: str | None, forced: list[str] | None = None) -> list[str]:
        if forced:
            candidates = forced
        elif zone == "toute_maison":
            candidates = []
            for zone_data in self.data.get("zones", {}).values():
                if zone_data.get("include_in_all", True):
                    candidates.extend(zone_data.get("speakers", []))
        elif zone and zone in self.data.get("zones", {}):
            candidates = list(self.data["zones"][zone].get("speakers", []))
        else:
            candidates = []
        unique: list[str] = []
        for entity_id in candidates:
            if isinstance(entity_id, str) and entity_id.startswith("media_player.") and entity_id not in unique:
                unique.append(entity_id)
        if not unique and self.data.get("fallback_to_default", True):
            fallback = str(self.data.get("default_speaker") or "")
            if fallback.startswith("media_player."):
                unique.append(fallback)
        return unique

    async def async_speak(self, message: str, *, zone: str | None = None, profile: str = "normal", speakers: list[str] | None = None, volume: float | None = None, voice: str | None = None, use_prefix: bool = True, tts_entity: str | None = None) -> dict[str, Any]:
        if not self.data.get("enabled", True):
            return {"ok": False, "reason": "disabled", "speakers": []}
        clean_message = str(message or "").strip()
        if not clean_message:
            return {"ok": False, "reason": "empty_message", "speakers": []}
        profile_name = profile if profile in PROFILE_NAMES else "normal"
        profile_data = self.data.get("profiles", {}).get(profile_name, {})
        tts = str(tts_entity or profile_data.get("tts_entity") or self.data.get("tts_entity") or "").strip()
        if not tts.startswith("tts."):
            return {"ok": False, "reason": "invalid_tts", "speakers": []}
        target_speakers = self.resolve_speakers(zone or "toute_maison", speakers)
        if not target_speakers:
            return {"ok": False, "reason": "no_speakers", "speakers": []}
        zone_volume = self.data["zones"][zone].get("volume") if zone and zone in self.data.get("zones", {}) else None
        effective_volume = volume if volume is not None else zone_volume
        if effective_volume is None:
            effective_volume = float(profile_data.get("volume", 0.40))
        effective_volume = max(0.0, min(1.0, float(effective_volume)))
        effective_voice = str(voice or profile_data.get("voice") or "").strip()
        prefix = str(self.data.get("prefix") or "").strip()
        spoken = f"{prefix} {clean_message}".strip() if use_prefix and prefix else clean_message
        is_google_ai = "google_ai" in tts or "google_generative_ai" in tts
        style = str(profile_data.get("style") or "").strip()
        if is_google_ai and style:
            spoken = f"{style} {spoken}"
        cache = bool(self.data.get("cache", True))
        successful: list[str] = []
        failed: dict[str, str] = {}
        original_volumes: dict[str, float] = {}

        async def _speak_one(entity_id: str) -> None:
            state = self.hass.states.get(entity_id)
            if state is None:
                failed[entity_id] = "entity_not_found"
                return
            if state.state in {"unknown", "unavailable"}:
                failed[entity_id] = state.state
                return
            old_volume = state.attributes.get("volume_level")
            if isinstance(old_volume, (int, float)):
                original_volumes[entity_id] = max(0.0, min(1.0, float(old_volume)))
            try:
                await self.hass.services.async_call("media_player", "volume_set", {"entity_id": entity_id, "volume_level": effective_volume}, blocking=True)
            except Exception as err:
                _LOGGER.debug("Volume set failed for %s: %s", entity_id, err)
            service_data: dict[str, Any] = {"entity_id": tts, "media_player_entity_id": entity_id, "message": spoken, "cache": cache}
            if is_google_ai and effective_voice:
                service_data["options"] = {"voice": effective_voice}
            try:
                await self.hass.services.async_call("tts", "speak", service_data, blocking=True)
                successful.append(entity_id)
            except Exception as err:
                failed[entity_id] = str(err)
                _LOGGER.warning("Voice Hub TTS failed on %s: %s", entity_id, err)

        async with self._speak_lock:
            await asyncio.gather(*(_speak_one(entity_id) for entity_id in target_speakers))
            estimated_seconds = min(10.0, max(2.0, (len(clean_message) + len(prefix)) / 14.0))
            await asyncio.sleep(estimated_seconds)
            if self.data.get("restore_volume", True) and original_volumes:
                async def _restore_one(entity_id: str, level: float) -> None:
                    try:
                        await self.hass.services.async_call("media_player", "volume_set", {"entity_id": entity_id, "volume_level": level}, blocking=True)
                    except Exception as err:
                        _LOGGER.debug("Volume restore failed for %s: %s", entity_id, err)
                await asyncio.gather(*(_restore_one(entity_id, level) for entity_id, level in original_volumes.items()))
        self.last_announcement = {"time": time.time(), "message": clean_message, "zone": zone or "toute_maison", "profile": profile_name, "speakers": successful, "failed": failed}
        return {"ok": bool(successful), "speakers": successful, "failed": failed}

    async def async_rebuild_rule_listener(self) -> None:
        if self._listener_unsub is not None:
            self._listener_unsub()
            self._listener_unsub = None
        entity_ids = sorted({str(rule.get("entity_id")) for rule in self.data.get("rules", []) if rule.get("enabled", True) and rule.get("entity_id")})
        if entity_ids:
            self._listener_unsub = async_track_state_change_event(self.hass, entity_ids, self._handle_state_change_event)

    def _handle_state_change_event(self, event: Event) -> None:
        self.hass.async_create_task(self._async_process_state_event(event))

    async def _async_process_state_event(self, event: Event) -> None:
        entity_id = event.data.get("entity_id")
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if not entity_id or time.monotonic() - self._started_monotonic < STARTUP_GRACE_SECONDS:
            return
        for rule in list(self.data.get("rules", [])):
            if not rule.get("enabled", True) or rule.get("entity_id") != entity_id:
                continue
            trigger_type = rule.get("trigger", "state")
            if trigger_type in {"state", "above", "below", "changed"} and (old_state is None or old_state.state in {"unknown", "unavailable"}):
                continue
            if trigger_type == "changed":
                new_match = new_state is not None and old_state is not None and new_state.state != old_state.state
                old_match = False
            else:
                new_match = self._rule_matches(rule, new_state)
                old_match = self._rule_matches(rule, old_state)
            if not new_match:
                task = self._pending.pop(str(rule.get("id")), None)
                if task:
                    task.cancel()
                continue
            if old_match and trigger_type != "changed":
                continue
            rule_id = str(rule.get("id"))
            pending = self._pending.pop(rule_id, None)
            if pending:
                pending.cancel()
            delay = max(0, int(rule.get("for_seconds") or 0))
            if delay:
                task = self.hass.async_create_task(self._async_delayed_rule(rule_id, entity_id, delay, old_state, new_state))
                self._pending[rule_id] = task
            else:
                await self._async_fire_rule(rule, old_state, new_state)

    async def _async_delayed_rule(self, rule_id: str, entity_id: str, delay: int, old_state: Any, new_state: Any) -> None:
        try:
            await asyncio.sleep(delay)
            rule = next((r for r in self.data.get("rules", []) if r.get("id") == rule_id and r.get("enabled", True)), None)
            if rule is None:
                return
            current_state = self.hass.states.get(entity_id)
            if self._rule_matches(rule, current_state):
                await self._async_fire_rule(rule, old_state, current_state or new_state)
        except asyncio.CancelledError:
            return
        finally:
            current_task = self._pending.get(rule_id)
            if current_task is asyncio.current_task():
                self._pending.pop(rule_id, None)

    def _rule_matches(self, rule: dict[str, Any], state: Any) -> bool:
        if state is None:
            return rule.get("trigger") == "unavailable"
        trigger_type = rule.get("trigger", "state")
        value = str(rule.get("value") or "")
        state_value = state.state
        if trigger_type == "state":
            return state_value == value
        if trigger_type == "above":
            try:
                return float(state_value) > float(value)
            except (TypeError, ValueError):
                return False
        if trigger_type == "below":
            try:
                return float(state_value) < float(value)
            except (TypeError, ValueError):
                return False
        if trigger_type == "available":
            return state_value not in {"unknown", "unavailable"}
        if trigger_type == "unavailable":
            return state_value in {"unknown", "unavailable"}
        if trigger_type == "changed":
            return True
        return False

    def _condition_matches(self, rule: dict[str, Any]) -> bool:
        entity_id = str(rule.get("condition_entity") or "").strip()
        operator = str(rule.get("condition_operator") or "").strip()
        value = str(rule.get("condition_value") or "").strip()
        if not entity_id or not operator:
            return True
        state = self.hass.states.get(entity_id)
        if state is None:
            return operator == "unavailable"
        current = state.state
        if operator == "state":
            return current == value
        if operator == "not_state":
            return current != value
        if operator == "above":
            try:
                return float(current) > float(value)
            except (TypeError, ValueError):
                return False
        if operator == "below":
            try:
                return float(current) < float(value)
            except (TypeError, ValueError):
                return False
        if operator in {"in", "not_in"}:
            values = {item.strip() for item in value.split(",") if item.strip()}
            result = current in values
            return result if operator == "in" else not result
        if operator == "available":
            return current not in {"unknown", "unavailable"}
        if operator == "unavailable":
            return current in {"unknown", "unavailable"}
        return True

    async def _async_fire_rule(self, rule: dict[str, Any], old_state: Any, new_state: Any) -> None:
        rule_id = str(rule.get("id"))
        now = time.monotonic()
        cooldown = max(0, int(rule.get("cooldown") or 0))
        if now - self._last_fired.get(rule_id, 0.0) < cooldown or not self._condition_matches(rule):
            return
        raw_message = str(rule.get("message") or "").strip()
        if not raw_message:
            return
        variables = {"trigger": {"entity_id": rule.get("entity_id"), "from_state": old_state, "to_state": new_state}, "entity_id": rule.get("entity_id")}
        try:
            rendered_message = str(Template(raw_message, self.hass).async_render(variables)).strip()
        except Exception as err:
            _LOGGER.warning("Voice rule %s template failed: %s", rule_id, err)
            rendered_message = raw_message
        result = await self.async_speak(rendered_message, zone=str(rule.get("zone") or "toute_maison"), profile=str(rule.get("profile") or "normal"))
        if result.get("ok"):
            self._last_fired[rule_id] = now
