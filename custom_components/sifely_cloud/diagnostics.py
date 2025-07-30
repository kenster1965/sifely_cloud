"""Diagnostics support for Sifely Cloud."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN

# Fields that should not appear in diagnostics
TO_REDACT = {
    "access_token",
    "login_token",
    "refresh_token",
    "User_Email",
    "User_Password",
    "clientId",
    "local_key",
    "deviceId",
    "noKeyPwd",
    "lockData",
    "id",
    "uuid",
    "token",
    "lockMac",
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
        "latest_status": getattr(coordinator, "latest_status", {}),
        "history_folder": getattr(coordinator, "history_path", "not set"),
        "update_interval": getattr(coordinator, "update_interval", "unknown"),
        "last_updated": getattr(coordinator, "last_updated", "unknown"),
    }

    return async_redact_data(diagnostics_data, TO_REDACT)
