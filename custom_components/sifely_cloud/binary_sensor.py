import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN, ENTITY_PREFIX
from .device import async_register_lock_device

_LOGGER = logging.getLogger(__name__)


def create_binary_sensors(locks, coordinator):
    """Create binary sensor entities for each lock."""
    entities = []
    for lock in locks:
        lock_id = lock.get("lockId")
        if lock_id:
            entities.append(SifelyPrivacyLockSensor(lock, coordinator))
            entities.append(SifelyTamperAlertSensor(lock, coordinator))
    return entities


class BaseSifelyBinarySensor(BinarySensorEntity):
    """Base class for all Sifely binary sensors."""
    def __init__(self, lock, coordinator):
        """Initialize shared attributes for binary sensors."""
        self.coordinator = coordinator
        self.lock_id = lock.get("lockId")
        self.alias = lock.get("lockAlias", "Sifely Lock")
        self.slug = slugify(self.alias)

        self._attr_device_info = async_register_lock_device(lock)
        self._attr_has_entity_name = True

    def update_state(self):
        """Update sensor state. Implement in subclass."""
        raise NotImplementedError

    async def async_update(self):
        """Fetch new state data for the sensor."""
        self.update_state()


class SifelyPrivacyLockSensor(BaseSifelyBinarySensor):
    """Binary sensor for detecting Privacy Lock mode."""
    def __init__(self, lock, coordinator):
        """Initialize the Privacy Lock sensor."""
        super().__init__(lock, coordinator)
        self._attr_translation_key = "privacy_mode"
        self._attr_unique_id = f"{ENTITY_PREFIX}_privacy_{self.slug}_{self.lock_id}"
        self._attr_icon = "mdi:shield-lock"

    @property
    def is_on(self):
        """Return True if privacy lock is enabled."""
        return self.coordinator.details_data.get(self.lock_id, {}).get("privacyLock") == 1

    def update_state(self):
        """Update internal state."""
        self._attr_is_on = self.is_on


class SifelyTamperAlertSensor(BaseSifelyBinarySensor):
    """Binary sensor for detecting Tamper Alert."""
    def __init__(self, lock, coordinator):
        """Initialize the Tamper Alert sensor."""
        super().__init__(lock, coordinator)
        self._attr_translation_key = "tamper_alert"
        self._attr_unique_id = f"{ENTITY_PREFIX}_tamper_{self.slug}_{self.lock_id}"
        self._attr_icon = "mdi:alert-octagram"

    @property
    def is_on(self):
        """Return True if tamper alert is active."""
        return self.coordinator.details_data.get(self.lock_id, {}).get("tamperAlert") == 1

    def update_state(self):
        """Update internal state."""
        self._attr_is_on = self.is_on


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up binary sensors for the Sifely Cloud integration."""
    _LOGGER.info("📟 Setting up Sifely binary sensors")

    coordinator = hass.data[DOMAIN].get("coordinator")
    if not coordinator:
        _LOGGER.warning("⚠️ Coordinator not found.")
        return

    sensors = create_binary_sensors(coordinator.data, coordinator)
    async_add_entities(sensors)

    _LOGGER.info("✅ %d binary sensors added", len(sensors))
