import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from datetime import datetime, timezone

from .const import DOMAIN, ENTITY_PREFIX, HISTORY_DISPLAY_LIMIT, HISTORY_RECORD_TYPES
from .device import async_register_lock_device

_LOGGER = logging.getLogger(__name__)


def create_sensors(locks: list[dict], coordinator) -> list[SensorEntity]:
    """Create all sensor entities for each lock."""
    entities = []
    for lock in locks:
        lock_id = lock.get("lockId")
        if lock_id:
            entities.append(SifelyBatterySensor(lock, coordinator))
            entities.append(SifelyLockHistorySensor(lock, coordinator))
            entities.append(SifelyCloudErrorSensor(lock, coordinator))
            entities.append(SifelyDiagnosticSensor(lock, coordinator))
        else:
            _LOGGER.warning("⚠️ Skipping sensor for lock with missing lockId: %s", lock)
    return entities


class SifelyBatterySensor(CoordinatorEntity, SensorEntity):
    """Battery level sensor for Sifely Smart Lock."""
    def __init__(self, lock_data: dict, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.lock_id = lock_data.get("lockId")
        self.alias = lock_data.get("lockAlias", f"{ENTITY_PREFIX} Lock")

        self._attr_name = f"{ENTITY_PREFIX}_{self.lock_id}_battery" if self.lock_id else self.alias
        self._attr_unique_id = f"{ENTITY_PREFIX.lower()}_{self.lock_id}_battery" if self.lock_id else None
        self._attr_translation_key = "battery"
        self._attr_translation_placeholders = {"name": self.alias}
        self._attr_has_entity_name = False
        self._attr_device_class = "battery"
        self._attr_native_unit_of_measurement = "%"
        self._attr_state_class = "measurement"
        self._attr_device_info = async_register_lock_device(lock_data)

    @property
    def native_value(self) -> int | None:
        lock_data = self.coordinator.details_data.get(self.lock_id, {})
        value = lock_data.get("electricQuantity")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                _LOGGER.warning("🔋 Invalid battery value for %s: %s", self.lock_id, value)
        return None

    @property
    def available(self) -> bool:
        return (
            self.lock_id is not None and
            self.lock_id in self.coordinator.details_data and
            "electricQuantity" in self.coordinator.details_data[self.lock_id]
        )


class SifelyLockHistorySensor(CoordinatorEntity, SensorEntity):
    """Sensor to display recent lock activity as text."""
    def __init__(self, lock_data: dict, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.lock_id = lock_data.get("lockId")
        self.alias = lock_data.get("lockAlias", f"{ENTITY_PREFIX} Lock")

        self._attr_name = f"{ENTITY_PREFIX}_{self.lock_id}_history" if self.lock_id else self.alias
        self._attr_unique_id = f"{ENTITY_PREFIX.lower()}_{self.lock_id}_history" if self.lock_id else None
        self._attr_translation_key = "history"
        self._attr_translation_placeholders = {"name": self.alias}
        self._attr_native_value = None
        self._attr_has_entity_name = False
        self._attr_icon = "mdi:history"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_extra_state_attributes = {}
        self._attr_device_info = async_register_lock_device(lock_data)

        if not hasattr(coordinator, "update_history_sensor"):
            coordinator.update_history_sensor = self._external_update

        self._latest_entries: list[dict] = []

    async def async_update(self):
        history = await self.coordinator.async_query_lock_history(self.lock_id)
        if not history:
            self._attr_native_value = "No recent activity"
            self._attr_extra_state_attributes = {}
            return

        lines = []
        attr_map = {}

        for i, entry in enumerate(history[:HISTORY_DISPLAY_LIMIT]):
            user = entry.get("username", "Unknown")
            ts = entry.get("lockDate")
            record_type = entry.get("recordType", "N/A")
            success = entry.get("success", -1)

            method = HISTORY_RECORD_TYPES.get(record_type, f"{record_type}")
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
        if lock_id != self.lock_id:
            return
        self._latest_entries = entries
        self._update_from_entries()
        self.async_write_ha_state()

    def _update_from_entries(self):
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

            method = HISTORY_RECORD_TYPES.get(record_type, f"{record_type}")
            formatted = f"{username} - {method} - {success}"

            attr_map[timestamp] = formatted
            if latest_value is None:
                latest_value = formatted

        self._attr_native_value = latest_value
        self._attr_extra_state_attributes = attr_map


class SifelyCloudErrorSensor(CoordinatorEntity, SensorEntity):
    """Sensor to indicate cloud communication errors."""
    def __init__(self, lock_data: dict, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.lock_id = lock_data.get("lockId")
        self.alias = lock_data.get("lockAlias", f"{ENTITY_PREFIX} Lock")

        self._attr_name = f"{ENTITY_PREFIX}_{self.lock_id}_error" if self.lock_id else self.alias
        self._attr_unique_id = f"{ENTITY_PREFIX.lower()}_{self.lock_id}_error" if self.lock_id else None
        self._attr_translation_key = "error"
        self._attr_translation_placeholders = {"name": self.alias}
        self._attr_has_entity_name = False
        self._attr_icon = "mdi:alert-circle"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
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


class SifelyDiagnosticSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor for Sifely lock metadata (firmware, hardware, etc.)."""

    def __init__(self, lock_data: dict, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.lock_data = lock_data

        self.alias = lock_data.get("lockAlias", f"{ENTITY_PREFIX} Lock")
        self.lock_id = lock_data.get("lockId")

        self._attr_name = f"{ENTITY_PREFIX}_{self.lock_id}_diagnostics" if self.lock_id else self.alias
        self._attr_unique_id = f"{ENTITY_PREFIX.lower()}_{self.lock_id}_diagnostics" if self.lock_id else None
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = async_register_lock_device(lock_data)

    @property
    def native_value(self) -> str | None:
        """Return a simple status for diagnostics."""
        details = self.coordinator.details_data.get(self.lock_id)
        return "OK" if details else "Unavailable"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional diagnostic attributes."""
        details = self.coordinator.details_data.get(self.lock_id, {})
        if not details:
            return {}

        return {
            "firmware_revision": details.get("firmwareRevision", "N/A"),
            "hardware_revision": details.get("hardwareRevision", "N/A"),
            "keyboard_pwd_version": details.get("keyboardPwdVersion", "N/A"),
            "has_gateway": details.get("hasGateway", False),
            "is_frozen": details.get("isFrozen", False),
            "passage_mode": details.get("passageMode", False),
            "lock_version": details.get("lockVersion", "N/A"),
        }


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    _LOGGER.info("🔋 Setting up Sifely sensors")

    coordinator = hass.data[DOMAIN].get("coordinator")
    if not coordinator:
        _LOGGER.warning("⚠️ No coordinator found for sensors")
        return

    all_entities = create_sensors(coordinator.data, coordinator)
    async_add_entities(all_entities)

    battery_count = sum(isinstance(e, SifelyBatterySensor) for e in all_entities)
    history_count = sum(isinstance(e, SifelyLockHistorySensor) for e in all_entities)
    error_count = sum(isinstance(e, SifelyCloudErrorSensor) for e in all_entities)
    diagnostic_count = sum(isinstance(e, SifelyDiagnosticSensor) for e in all_entities)

    if all_entities:
        _LOGGER.info("✅ %d total sensors added.", len(all_entities))
        if battery_count:
            _LOGGER.info("🔋 %d battery sensors added.", battery_count)
        if history_count:
            _LOGGER.info("📜 %d history sensors added.", history_count)
        if error_count:
            _LOGGER.info("🚨 %d error sensors added.", error_count)
        if diagnostic_count:
            _LOGGER.info("🩺 %d diagnostic sensors added.", diagnostic_count)
    else:
        _LOGGER.warning("⚠️ No sensors found to set up.")
