"""Constants for HA Voice Hub."""

DOMAIN = "maison_alain_voice_hub"
VERSION = "1.0.1"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STARTUP_GRACE_SECONDS = 90

SERVICE_SPEAK = "speak"
SERVICE_RELOAD = "reload"

PANEL_NAME = "maison-alain-voice-hub-panel"
PANEL_URL_PATH = "maison-alain-voice-hub"
PANEL_TITLE = "Admin Voix"
PANEL_ICON = "mdi:account-voice"
PANEL_STATIC_URL = "/maison_alain_voice_hub_static.js"
PANEL_FILENAME = "voice-hub.js"

# Community edition: no user-specific entity is hard-coded.
# The setup flow requires the user to choose a TTS entity and a fallback media player.
DEFAULT_TTS_ENTITY = ""
DEFAULT_SPEAKER = ""
DEFAULT_PREFIX = ""
DEFAULT_VOICE = "zephyr"

PROFILE_NAMES = ("discret", "normal", "important", "critique")

DEFAULT_PROFILES = {
    "discret": {
        "volume": 0.25,
        "voice": DEFAULT_VOICE,
        "tts_entity": "",
        "style": "Parle doucement, calmement et clairement en français :",
    },
    "normal": {
        "volume": 0.40,
        "voice": DEFAULT_VOICE,
        "tts_entity": "",
        "style": "Parle clairement et naturellement en français :",
    },
    "important": {
        "volume": 0.55,
        "voice": DEFAULT_VOICE,
        "tts_entity": "",
        "style": "Parle de façon ferme, claire et attentive en français :",
    },
    "critique": {
        "volume": 0.70,
        "voice": DEFAULT_VOICE,
        "tts_entity": "",
        "style": "Parle de façon urgente, très claire et concise en français :",
    },
}

# Generic starter zones only. Everything can be renamed/deleted from Admin Voix.
DEFAULT_ZONES = {
    "portable": {
        "name": "Portable / test",
        "icon": "mdi:laptop",
        "speakers": [],
        "volume": None,
        "include_in_all": False,
    },
    "salon": {
        "name": "Salon",
        "icon": "mdi:sofa",
        "speakers": [],
        "volume": None,
        "include_in_all": True,
    },
    "cuisine": {
        "name": "Cuisine",
        "icon": "mdi:countertop-outline",
        "speakers": [],
        "volume": None,
        "include_in_all": True,
    },
    "chambre": {
        "name": "Chambre",
        "icon": "mdi:bed-king-outline",
        "speakers": [],
        "volume": None,
        "include_in_all": True,
    },
    "bureau": {
        "name": "Bureau",
        "icon": "mdi:desk",
        "speakers": [],
        "volume": None,
        "include_in_all": True,
    },
    "entree": {
        "name": "Entrée",
        "icon": "mdi:door",
        "speakers": [],
        "volume": None,
        "include_in_all": True,
    },
    "exterieur": {
        "name": "Extérieur",
        "icon": "mdi:tree",
        "speakers": [],
        "volume": None,
        "include_in_all": False,
    },
}

# Community edition ships with no active rules to avoid unexpected announcements
# or references to entities that do not exist on another Home Assistant instance.
DEFAULT_RULES = []
