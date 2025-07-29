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

    # Parse lock version fields
    # version_info = lock_data.get("lockVersion", {})
    # sw_version = None
    # hw_version = None

    # if isinstance(version_info, dict):
    #     protocol_version = version_info.get("protocolVersion")
    #     protocol_type = version_info.get("protocolType")
    #     scene = version_info.get("scene")
    #     group_id = version_info.get("groupId")

    #     if protocol_version is not None and protocol_type is not None:
    #         sw_version = f"{protocol_version}.{protocol_type}"

    #     if scene is not None and group_id is not None:
    #         hw_version = f"Scene {scene}, Group {group_id}"

    connections = {("mac", mac)} if mac and ":" in mac else set()

    return DeviceInfo(
        identifiers={(DOMAIN, str(lock_id))},
        name=alias,
        manufacturer="Sifely",
        model=model,
        #sw_version=sw_version,
        #hw_version=hw_version,
        connections=connections,
    )
