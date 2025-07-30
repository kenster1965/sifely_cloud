"""Diagnostics support for Sifely Cloud."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN, VERSION, CONF_APX_NUM_LOCKS, CONF_HISTORY_ENTRIES, DETAILS_UPDATE_INTERVAL, \
    STATE_QUERY_INTERVAL, HISTORY_INTERVAL, HISTORY_DISPLAY_LIMIT, LOCK_REQUEST_RETRIES, TOKEN_REFRESH_BUFFER_MINUTES, \
    TOKEN_401s_BEFORE_REAUTH, TOKEN_401s_BEFORE_ALERT, API_BASE_URL, TOKEN_ENDPOINT, REFRESH_ENDPOINT, KEYLIST_ENDPOINT, \
    LOCK_DETAIL_ENDPOINT, QUERY_STATE_ENDPOINT, UNLOCK_ENDPOINT, LOCK_ENDPOINT, LOCK_HISTORY_ENDPOINT, \
    HISTORY_RECORD_TYPES, VALID_ENTITY_CATEGORIES


# Fields that should not appear in diagnostics
TO_REDACT = {
    "access_token",
    "login_token",
    "refresh_token",
    "User_Email",
    "User_Password",
    "adminPwd",
    "clientId",
    "local_key",
    "lockKey",
    "deviceId",
    "noKeyPwd",
    "lockData",
    "id",
    "uuid",
    "token",
    "lockMac",
    "aesKeyStr",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""

    coordinator = hass.data.get(DOMAIN, {}).get("coordinator")

    if coordinator is None:
        return {
            "error": "Coordinator not found",
            "config_entry": async_redact_data(
                {
                    "title": entry.title,
                    "data": entry.data,
                    "options": entry.options,
                },
                TO_REDACT,
            ),
        }

    diagnostics_data = {
        "config_entry": {
            "title": entry.title,
            "data": entry.data,
            "options": entry.options,
        },
        "locks_data": coordinator.data,
        "details_data": getattr(coordinator, "details_data", {}),
        "latest_status": getattr(coordinator, "latest_status", {}),
        "history_folder": getattr(coordinator, "history_path", "not set"),
        "update_interval": getattr(coordinator, "update_interval", "unknown"),
        "last_updated": getattr(coordinator, "last_updated", "unknown"),

    "constants": {
        "DOMAIN": DOMAIN,
        "CONF_APX_NUM_LOCKS": entry.options.get(CONF_APX_NUM_LOCKS, "not set"),
        "CONF_HISTORY_ENTRIES": entry.options.get(CONF_HISTORY_ENTRIES, "not set"),
        "VERSION": VERSION,
        "DETAILS_UPDATE_INTERVAL": DETAILS_UPDATE_INTERVAL,
        "STATE_QUERY_INTERVAL": STATE_QUERY_INTERVAL,
        "HISTORY_INTERVAL": HISTORY_INTERVAL,
        "HISTORY_DISPLAY_LIMIT": HISTORY_DISPLAY_LIMIT,
        "LOCK_REQUEST_RETRIES": LOCK_REQUEST_RETRIES,
        "TOKEN_REFRESH_BUFFER_MINUTES": TOKEN_REFRESH_BUFFER_MINUTES,
        "TOKEN_401s_BEFORE_REAUTH": TOKEN_401s_BEFORE_REAUTH,
        "TOKEN_401s_BEFORE_ALERT": TOKEN_401s_BEFORE_ALERT,
        "API_BASE_URL": API_BASE_URL,
        "TOKEN_ENDPOINT": TOKEN_ENDPOINT,
        "REFRESH_ENDPOINT": REFRESH_ENDPOINT,
        "KEYLIST_ENDPOINT": KEYLIST_ENDPOINT,
        "LOCK_DETAIL_ENDPOINT": LOCK_DETAIL_ENDPOINT,
        "QUERY_STATE_ENDPOINT": QUERY_STATE_ENDPOINT,
        "UNLOCK_ENDPOINT": UNLOCK_ENDPOINT,
        "LOCK_ENDPOINT": LOCK_ENDPOINT,
        "LOCK_HISTORY_ENDPOINT": LOCK_HISTORY_ENDPOINT,
        "HISTORY_RECORD_TYPES": HISTORY_RECORD_TYPES,
    }

    }

    return async_redact_data(diagnostics_data, TO_REDACT)
