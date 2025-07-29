import logging
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def async_register_lock_device(lock_data: dict) -> DeviceInfo:
    """Create and return DeviceInfo for a Sifely lock entity."""

    lock_id = lock_data.get("lockId")
    alias = lock_data.get("lockAlias", "Sifely Lock")
    mac = lock_data.get("lockMac")
    model = lock_data.get("lockName", "Sifely")

    if not lock_id:
        _LOGGER.warning("⚠️ Lock data missing 'lockId': %s", lock_data)

    # Normalize MAC
    if mac:
        mac = mac.lower()

    connections = {("mac", mac)} if mac and ":" in mac else set()

    return DeviceInfo(
        identifiers={(DOMAIN, str(lock_id))},
        name=alias,
        manufacturer="Sifely",
        model=model,
        connections=connections,
    )
