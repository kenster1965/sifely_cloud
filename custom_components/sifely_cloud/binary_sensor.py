import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

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


class BaseSifelyBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for all Sifely binary sensors."""
    def __init__(self, lock, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.lock_id = lock.get("lockId")
        self.alias = lock.get("lockAlias", "Sifely Lock")

        self._attr_device_info = async_register_lock_device(lock)
        self._attr_has_entity_name = False

    def update_state(self):
        raise NotImplementedError

    async def async_update(self):
        self.update_state()

    @property
    def details(self) -> dict:
        """Return normalized details for this lock."""
        return self.coordinator.details_data.get(self.lock_id, {})


class SifelyPrivacyLockSensor(BaseSifelyBinarySensor):
    """Binary sensor for detecting Privacy Mode."""
    def __init__(self, lock_data: dict, coordinator: DataUpdateCoordinator):
        super().__init__(lock_data, coordinator)
        self._attr_name = f"{ENTITY_PREFIX}_{self.lock_id}_privacy" if self.lock_id else self.alias
        self._attr_unique_id = f"{ENTITY_PREFIX.lower()}_{self.lock_id}_privacy" if self.lock_id else None
        self._attr_translation_key = "privacy_mode"
        self._attr_translation_placeholders = {"name": self.alias}
        self._attr_icon = "mdi:shield-lock"

    @property
    def is_on(self):
        return self.details.get("privacyLock") == 1

    def update_state(self):
        self._attr_is_on = self.is_on


class SifelyTamperAlertSensor(BaseSifelyBinarySensor):
    """Binary sensor for detecting Tamper Alert."""
    def __init__(self, lock_data: dict, coordinator: DataUpdateCoordinator):
        super().__init__(lock_data, coordinator)
        self._attr_name = f"{ENTITY_PREFIX}_{self.lock_id}_tamper" if self.lock_id else self.alias
        self._attr_unique_id = f"{ENTITY_PREFIX.lower()}_{self.lock_id}_tamper" if self.lock_id else None
        self._attr_translation_key = "tamper_alert"
        self._attr_translation_placeholders = {"name": self.alias}
        self._attr_icon = "mdi:alert-octagram"

    @property
    def is_on(self):
        return self.details.get("tamperAlert") == 1

    def update_state(self):
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
