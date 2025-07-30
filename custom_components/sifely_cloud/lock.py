import logging

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, ENTITY_PREFIX
from .device import async_register_lock_device

_LOGGER = logging.getLogger(__name__)


def create_lock_entities(locks: list[dict], coordinator: DataUpdateCoordinator) -> list[LockEntity]:
    """Create lock entities from Sifely lock data."""
    entities = []
    for lock in locks:
        lock_id = lock.get("lockId")
        if lock_id:
            entities.append(SifelySmartLock(lock, coordinator))
        else:
            _LOGGER.warning("⚠️ Skipping lock with missing lockId: %s", lock)
    return entities


class SifelySmartLock(LockEntity):
    """Representation of a Sifely Smart Lock."""

    def __init__(self, lock_data: dict, coordinator: DataUpdateCoordinator):
        """Initialize the Lock."""
        self.coordinator = coordinator
        self.lock_data = lock_data

        self.lock_id = lock_data.get("lockId")
        self.alias = lock_data.get("lockAlias", f"{ENTITY_PREFIX} Lock")

        self._attr_name = f"{ENTITY_PREFIX}_{self.lock_id}_lock" if self.lock_id else self.alias
        self._attr_unique_id = f"{ENTITY_PREFIX.lower()}_{self.lock_id}_lock" if self.lock_id else None
        self._attr_translation_key = "lock"
        self._attr_translation_placeholders = {"name": self.alias}
        self._attr_device_info = async_register_lock_device(lock_data)

    @property
    def is_locked(self) -> bool | None:
        """Return True if locked, False if unlocked, None if unknown."""
        if not self.lock_id:
            return None

        state = self.coordinator.open_state_data.get(self.lock_id)
        # Sifely: 0 = locked, 1 = unlocked
        return True if state == 0 else False if state == 1 else None

    async def async_lock(self, **kwargs):
        """Send lock command to the device."""
        if not self.lock_id:
            _LOGGER.warning("🔒 Cannot lock: Missing lockId")
            return

        _LOGGER.info("🔒 Lock command issued for %s", self.alias)
        await self.coordinator.async_send_lock_command(self.lock_id, lock=True)
        await self.coordinator.async_query_open_state()
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        """Send unlock command to the device."""
        if not self.lock_id:
            _LOGGER.warning("🔓 Cannot unlock: Missing lockId")
            return

        _LOGGER.info("🔓 Unlock command issued for %s", self.alias)
        await self.coordinator.async_send_lock_command(self.lock_id, lock=False)
        await self.coordinator.async_query_open_state()
        self.async_write_ha_state()

    @property
    def available(self):
        return self.lock_id is not None and self.lock_id in self.coordinator.open_state_data

    async def async_update(self):
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Handle entity addition."""
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))

    def _handle_coordinator_update(self):
        """Called when coordinator updates data."""
        for updated_lock in self.coordinator.data:
            if updated_lock.get("lockId") == self.lock_id:
                self.lock_data = updated_lock
                break
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sifely lock entities."""
    _LOGGER.info("🔐 Setting up Sifely locks")

    coordinator = hass.data[DOMAIN].get("coordinator")
    if not coordinator:
        _LOGGER.warning("⚠️ No coordinator found for Sifely locks")
        return

    entities = create_lock_entities(coordinator.data, coordinator)
    async_add_entities(entities)

    if entities:
        _LOGGER.info("🔐 %d Sifely locks added.", len(entities))
    else:
        _LOGGER.warning("⚠️ No Sifely locks found to set up.")
