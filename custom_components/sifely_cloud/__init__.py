# __init__.py
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_API_KEY,
    DOMAIN,
    STARTUP_MESSAGE,
    SUPPORTED_PLATFORMS,
)
from .sifely import setup_sifely_coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Handle YAML setup (unused)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle integration setup from config flow."""
    _LOGGER.info("📦 Setting up Sifely Cloud with options: %s", entry.options)

    hass.data.setdefault(DOMAIN, {})
    _LOGGER.info(STARTUP_MESSAGE)

    # Extract credentials from config entry options
    api_key = entry.options.get(CONF_API_KEY)

    if not api_key:
        _LOGGER.error("❌ Missing API key in config entry.")
        return False

    # Create and initialize coordinator
    try:
        coordinator = await setup_sifely_coordinator(hass, api_key, entry)
        _LOGGER.info("✅ Sifely coordinator initialized successfully.")
    except Exception as e:
        _LOGGER.exception("❌ Failed to initialize Sifely integration")
        return False

    # Store coordinator under entry ID
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    # ✅ Listen for config option updates
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)

    return True


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update by reloading the config entry."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_refresh_lock_list(hass: HomeAssistant):
    """Manually trigger a refresh of the lock list."""
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        coordinator = data.get("coordinator")
        if coordinator:
            await coordinator.async_fetch_lock_list()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, SUPPORTED_PLATFORMS)

    return unload_ok
