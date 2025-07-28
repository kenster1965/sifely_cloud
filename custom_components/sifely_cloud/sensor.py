import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import slugify
from datetime import datetime, timezone

from .const import DOMAIN, ENTITY_PREFIX, HISTORY_DISPLAY_LIMIT, HISTORY_RECORD_TYPES
from .device import async_register_lock_device

_LOGGER = logging.getLogger(__name__)


def create_battery_entities(locks: list[dict], coordinator) -> list[SensorEntity]:
    """Create battery sensor entities for each lock."""
    entities = []
    for lock in locks:
        if lock.get("lockId") is not None:
            entities.append(SifelyBatterySensor(lock, coordinator))
        else:
            _LOGGER.warning("⚠️ Skipping battery sensor for lock with missing lockId: %s", lock)
    return entities

def create_history_entities(locks: list[dict], coordinator) -> list[SensorEntity]:
    """Create lock history sensor entities for each lock."""
    entities = []
    for lock in locks:
        if lock.get("lockId") is not None:
            entities.append(SifelyLockHistorySensor(lock, coordinator))
        else:
            _LOGGER.warning("⚠️ Skipping history sensor for lock with missing lockId: %s", lock)
    return entities

def create_error_entities(locks: list[dict], coordinator) -> list[SensorEntity]:
    """Create cloud error sensor entities for each lock."""
    entities = []
    for lock in locks:
        if lock.get("lockId") is not None:
            entities.append(SifelyCloudErrorSensor(lock, coordinator))
        else:
            _LOGGER.warning("⚠️ Skipping error sensor for lock with missing lockId: %s", lock)
    return entities


class SifelyBatterySensor(CoordinatorEntity, SensorEntity):
    """Battery level sensor for Sifely Smart Lock."""
    _attr_translation_key = "battery"
    _attr_has_entity_name = True
    _attr_device_class = "battery"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = "measurement"

    def __init__(self, lock_data: dict, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.lock_data = lock_data

        alias = lock_data.get("lockAlias", "Sifely Lock")
        slug = slugify(alias)
        lock_id = lock_data.get("lockId")

        self._attr_unique_id = f"{ENTITY_PREFIX}_battery_{slug}_{lock_id}"
        self._attr_device_info = async_register_lock_device(lock_data)

    @property
    def native_value(self) -> int | None:
        """Return the current battery level."""
        lock_id = self.lock_data.get("lockId")
        details = self.coordinator.details_data.get(lock_id)
        if not details:
            return None
        return details.get("electricQuantity")

    @property
    def available(self):
        """Battery sensor is only available if lockId is known."""
        lock_id = self.lock_data.get("lockId")
        return lock_id is not None and lock_id in self.coordinator.details_data


class SifelyLockHistorySensor(CoordinatorEntity, SensorEntity):
    """Sensor to display recent lock activity as text."""
    _attr_translation_key = "history"
    _attr_has_entity_name = True
    _attr_icon = "mdi:history"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, lock_data: dict, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.lock_data = lock_data

        alias = lock_data.get("lockAlias", "Sifely Lock")
        slug = slugify(alias)
        lock_id = lock_data.get("lockId")

        self.lock_id = lock_id
        self.slug = slug

        self._attr_unique_id = f"{ENTITY_PREFIX}_history_{slug}_{lock_id}"
        self._attr_device_info = async_register_lock_device(lock_data)
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

        if not hasattr(coordinator, "update_history_sensor"):
            coordinator.update_history_sensor = self._external_update

        self._latest_entries: list[dict] = []

    async def async_update(self):
        """Fetch latest lock history from coordinator."""
        history = await self.coordinator.async_query_lock_history(self.lock_id)

        if not history:
            self._attr_native_value = "No recent activity"
            self._attr_extra_state_attributes = {}
            return

        # Create a summary string (last user, time, type)
        lines = []
        attr_map = {}

        for i, entry in enumerate(history[:HISTORY_DISPLAY_LIMIT]):
            user = entry.get("username", "Unknown")
            ts = entry.get("lockDate")
            record_type = entry.get("recordType", "N/A")
            success = entry.get("success", -1)

            # Map record type to readable name
            method = HISTORY_RECORD_TYPES.get(record_type, f"Type {record_type}")
            success_text = "✅ Success" if success == 1 else "❌ Failed"

            try:
                dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).astimezone()
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                formatted_time = str(ts)

            line = f"{formatted_time}: {user} via {method} — {success_text}"
            lines.append(line)
            attr_map[f"entry_{i+1}"] = line

        self._attr_native_value = lines[0] if lines else "No recent activity"
        self._attr_extra_state_attributes = attr_map

    async def _external_update(self, lock_id, entries):
        """Receive external history data from the coordinator."""
        if lock_id != self.lock_id:
            return

        self._latest_entries = entries
        self._update_from_entries()
        self.async_write_ha_state()

    def _update_from_entries(self):
        """Set sensor state and attributes from latest_entries."""
        if not self._latest_entries:
            self._attr_native_value = "No recent activity"
            self._attr_extra_state_attributes = {}
            return

        attr_map = {}
        latest_value = None

        for entry in self._latest_entries:
            timestamp = entry.get("lockDate")
            username = entry.get("username", "Unknown")
            record_type = entry.get("recordType", "N/A")
            success = entry.get("success", "Unknown")

            method = HISTORY_RECORD_TYPES.get(record_type, f"Type {record_type}")
            formatted = f"{username} - {method} - {success}"

            # Use timestamp as the key (ensures clean UI labels)
            attr_map[timestamp] = formatted
            if latest_value is None:
                latest_value = formatted

        self._attr_native_value = latest_value
        self._attr_extra_state_attributes = attr_map


class SifelyCloudErrorSensor(CoordinatorEntity, SensorEntity):
    """Sensor to indicate cloud communication errors."""
    _attr_translation_key = "error"
    _attr_has_entity_name = True
    _attr_icon = "mdi:alert-circle"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, lock_data: dict, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.lock_data = lock_data
        self.lock_id = lock_data.get("lockId")
        alias = lock_data.get("lockAlias", "Sifely Lock")
        slug = slugify(alias)

        self._attr_unique_id = f"{ENTITY_PREFIX}_error_{slug}_{self.lock_id}"
        self._attr_native_value = "OK"
        self._attr_extra_state_attributes = {}
        self._attr_device_info = async_register_lock_device(lock_data)

        coordinator.set_cloud_error = self.set_error
        coordinator.clear_cloud_error = self.clear_error

    def set_error(self, message: str):
        self._attr_native_value = "Error"
        self._attr_extra_state_attributes = {"last_error": message}
        if self.hass:
            self.async_write_ha_state()
        else:
            _LOGGER.warning("⚠️ Cannot update error sensor — hass is None")

    def clear_error(self):
        self._attr_native_value = "OK"
        self._attr_extra_state_attributes = {}
        if self.hass:
            self.async_write_ha_state()
        else:
            _LOGGER.warning("⚠️ Cannot clear error sensor — hass is None")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sifely sensors (battery + history)."""
    _LOGGER.info("🔋 Setting up Sifely sensors")

    coordinator = hass.data[DOMAIN].get("coordinator")
    if not coordinator:
        _LOGGER.warning("⚠️ No coordinator found for sensors")
        return

    battery_entities = create_battery_entities(coordinator.data, coordinator)
    history_entities = create_history_entities(coordinator.data, coordinator)
    error_entities = create_error_entities(coordinator.data, coordinator)

    all_entities = battery_entities + history_entities + error_entities
    async_add_entities(all_entities)

    if battery_entities:
        _LOGGER.info("🔋 %d battery sensors added.", len(battery_entities))
    if history_entities:
        _LOGGER.info("📜 %d history sensors added.", len(history_entities))
    if error_entities:
        _LOGGER.info("🚨 %d error sensors added.", len(error_entities))
    if not all_entities:
        _LOGGER.warning("⚠️ No sensors found to set up.")
