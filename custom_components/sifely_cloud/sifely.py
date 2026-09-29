# sifely.py (with lock/unlock command support)

import logging
import json
from datetime import datetime, timezone, timedelta
from .history_utils import fetch_and_update_lock_history

from homeassistant.util import dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


from .const import (
    DOMAIN, CONF_APX_NUM_LOCKS, LOCK_REQUEST_RETRIES, STATE_QUERY_INTERVAL, DETAILS_UPDATE_INTERVAL, \
    HISTORY_DISPLAY_LIMIT, HISTORY_INTERVAL, LOCK_LIST_ENDPOINT, LOCK_DETAIL_ENDPOINT, \
    QUERY_STATE_ENDPOINT, LOCK_ENDPOINT, UNLOCK_ENDPOINT,LOCK_HISTORY_ENDPOINT, \
    TOKEN_401s_BEFORE_REAUTH, TOKEN_401s_BEFORE_ALERT
)

_LOGGER = logging.getLogger(__name__)

HISTORY_FOLDER = "history"

class SifelyCoordinator(DataUpdateCoordinator):
    """Coordinates updates for Sifely locks."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        config_entry,
    ):
        self.hass = hass
        self.config_entry = config_entry
        self.session = async_get_clientsession(hass)
        self.apx_locks = config_entry.options.get(CONF_APX_NUM_LOCKS, 5)

        self.last_details_update = datetime.min.replace(tzinfo=timezone.utc)
        self.lock_list = []
        self.details_data = {}
        self.open_state_data = {}
        self._consecutive_401s = 0
        self.headers = {
            "Authorization": api_key,
        }

        super().__init__(
            hass,
            _LOGGER,
            name="sifely_lock_coordinator",
            # update_interval is disabled; polling is done manually via async_track_time_interval
        )

    async def _async_update_data(self):
        """Disabled auto-update mechanism (we handle it manually)."""
        return self.lock_list

    async def async_fetch_lock_list(self):
        """Get lock data from the Sifely API."""
        params = {
            "pageNo": 1,
            "pageSize": self.apx_locks,
        }

        try:
            _LOGGER.debug("📡 Fetching lock list from: %s", LOCK_LIST_ENDPOINT)
            async with self.session.post(LOCK_LIST_ENDPOINT, headers=self.headers, params=params) as resp:
                text = await resp.text()
                _LOGGER.debug("🔑 Lock list raw response: %s", text)

                try:
                    data = json.loads(text)
                except Exception as e:
                    raise UpdateFailed(f"Failed to parse lock list response: {e}")

                if resp.status != 200 or "list" not in data:
                    raise UpdateFailed(f"Unexpected lock list response: {data}")

                locks = data["list"]
                self.lock_list = locks
                _LOGGER.info("✅ Fetched %d locks", len(locks))
                return locks

        except Exception as e:
            _LOGGER.exception("🚨 Failed to fetch lock list: %s", str(e))
            raise UpdateFailed(f"Exception fetching locks: {str(e)}")

    async def async_query_open_state(self):
        """Query open/locked state for each lock and store in self.open_state_data."""
        if not self.lock_list:
            _LOGGER.debug("⏩ Skipping open state polling: lock list not available")
            return

        if not hasattr(self, "_consecutive_401s"):
            self._consecutive_401s = 0

        for lock in self.lock_list:
            lock_id = lock.get("lockId")
            if not lock_id:
                _LOGGER.warning("🔑 Skipping lock with missing lockId: %s", lock)
                continue

            params = { "lockId": lock_id }
            
            try:
                async with self.session.get(QUERY_STATE_ENDPOINT, headers=self.headers, params=params) as resp:
                    text = await resp.text()
                    _LOGGER.debug("🔒 Open state response for %s: %s", lock_id, text)

                    try:
                        data = json.loads(text)

                        if resp.status == 200:
                            self._consecutive_401s = 0
                            if hasattr(self, "clear_cloud_error"):
                                self.clear_cloud_error()

                            if "state" in data:
                                self.open_state_data[lock_id] = data.get("state")
                            else:
                                _LOGGER.warning("⚠️ Unknown open state format for %s: %s", lock_id, data)

                        elif resp.status == 401:
                            self._consecutive_401s += 1
                            _LOGGER.warning("⚠️ Received 401 (#%d) when fetching state for %s", self._consecutive_401s, lock_id)

                            if self._consecutive_401s == TOKEN_401s_BEFORE_REAUTH:
                                _LOGGER.warning(f"🔁 Detected {TOKEN_401s_BEFORE_REAUTH} consecutive 401s.")
                        
                            if self._consecutive_401s >= TOKEN_401s_BEFORE_ALERT:
                                if hasattr(self, "set_cloud_error"):
                                    self.set_cloud_error(f"Exceeded {TOKEN_401s_BEFORE_ALERT} consecutive 401 errors. Token likely invalid.")

                        else:
                            _LOGGER.warning("⚠️ HTTP %d when fetching state for %s: %s", resp.status, lock_id, text)

                    except Exception as e:
                        _LOGGER.warning("❌ Failed to parse open state for %s: %s", lock_id, e)

            except Exception as e:
                _LOGGER.warning("🚫 Failed to fetch open state for %s: %s", lock_id, e)


    async def async_query_lock_details(self) -> dict:
        """Query detailed lock info for each lock and store in self.details_data."""
        self.details_data = {}  # Reset it fresh each call

        if not self.lock_list:
            _LOGGER.debug("⏩ Skipping lock detail polling: lock list not available")
            return self.details_data

        for lock in self.lock_list:
            lock_id = lock.get("lockId")
            if not lock_id:
                _LOGGER.warning("🔑 Skipping lock with missing lockId: %s", lock)
                continue

            params = { "lockId": lock_id }
            try:
                async with self.session.get(LOCK_DETAIL_ENDPOINT, headers=self.headers, params=params) as resp:
                    text = await resp.text()
                    _LOGGER.debug("🔍 Lock detail response for %s: %s", lock_id, text)

                    try:
                        data = json.loads(text)

                        if resp.status == 200:
                            if "lockId" in data:
                                self.details_data[lock_id] = data
                                _LOGGER.debug("ℹ️ Parsed lock detail for %s", lock_id)
                            else:
                                _LOGGER.warning("⚠️ Unexpected lock detail format for %s: %s", lock_id, data)

                        else:
                            _LOGGER.warning("🚫 Non-200 HTTP status %s for lock %s", resp.status, lock_id)

                    except Exception as e:
                        _LOGGER.warning("❌ Failed to parse lock detail for %s: %s", lock_id, e)

            except Exception as e:
                _LOGGER.warning("🚫 Failed to fetch lock detail for %s: %s", lock_id, e)

        return self.details_data  # ✅ Explicit return


    async def async_send_lock_command(self, lock_id: int, lock: bool) -> bool:
        """Send a lock or unlock command to a specific lock."""
        endpoint = LOCK_ENDPOINT if lock else UNLOCK_ENDPOINT
        params = { "lockId": lock_id }
  
        for attempt in range(1, LOCK_REQUEST_RETRIES + 1):
            try:
                async with self.session.post(endpoint, headers=self.headers, params=params) as resp:
                    text = await resp.text()
                    _LOGGER.debug("🔐 Lock command response (attempt %d) for %s: %s", attempt, lock_id, text)

                    try:
                        result = json.loads(text)
                        if resp.status == 200 and result.get("errcode") == 0:
                            _LOGGER.info("✅ Successfully sent %s command to lock %s", "lock" if lock else "unlock", lock_id)
                            return True
                        else:
                            _LOGGER.warning("⚠️ Failed to %s lock %s (attempt %d): %s", "lock" if lock else "unlock", lock_id, attempt, result)
                    except Exception as e:
                        _LOGGER.warning("❌ Failed to parse %s response for lock %s: %s", "lock" if lock else "unlock", lock_id, e)

            except Exception as e:
                _LOGGER.warning("🚫 Request error on %s command attempt %d for lock %s: %s", "lock" if lock else "unlock", attempt, lock_id, e)

        return False  # All retries failed

    async def async_query_lock_history(self, lock_id: int) -> list:
        """Fetch lock history records for a given lock."""
        params = { "lockId": lock_id, "pageNo": 1, "pageSize": HISTORY_DISPLAY_LIMIT }
        try:
            async with self.session.get(LOCK_HISTORY_ENDPOINT, headers=self.headers, params=params) as resp:
                text = await resp.text()
                _LOGGER.debug("📜 Lock history response for %s: %s", lock_id, text)

                data = json.loads(text)
                if resp.status == 200 and "list" in data:
                    return data["list"]
                else:
                    _LOGGER.warning("⚠️ Unexpected lock history for %s: %s", lock_id, data)
                    return []

        except Exception as e:
            _LOGGER.warning("❌ Failed to fetch lock history for %s: %s", lock_id, e)
            return []

    def set_cloud_error(self, message: str):
        """Set the error sensor to an alert state."""
        if hasattr(self, "error_sensor") and self.error_sensor:
            self.error_sensor.native_value = "Error"
            self.error_sensor._attr_extra_state_attributes["last_error"] = message

            if self.error_sensor.hass:
                self.error_sensor.async_schedule_update_ha_state()
            else:
                _LOGGER.warning("⚠️ Cannot update error sensor — hass is None")

    def clear_cloud_error(self):
        """Clear the error sensor state."""
        if hasattr(self, "error_sensor") and self.error_sensor:
            self.error_sensor.native_value = "OK"
            self.error_sensor._attr_extra_state_attributes = {}

            if self.error_sensor.hass:
                self.error_sensor.async_schedule_update_ha_state()
            else:
                _LOGGER.warning("⚠️ Cannot clear error sensor — hass is None")



async def setup_sifely_coordinator(
    hass: HomeAssistant,
    api_key,
    config_entry,
) -> SifelyCoordinator:
    """Initialize, refresh, and store the coordinator."""
    coordinator = SifelyCoordinator(hass, api_key, config_entry)

    # 📡 Step 1: Fetch initial lock list
    locks = await coordinator.async_fetch_lock_list()
    coordinator.data = locks  # 🔥 Set initial data for entities

    # 🔋 Step 2: Immediately fetch lock details (so battery sensors are ready)
    coordinator.details_data = await coordinator.async_query_lock_details()

    # 💾 Register the coordinator globally
    hass.data.setdefault(DOMAIN, {})["coordinator"] = coordinator

    # 🆕 RUN HISTORY UPDATE ONCE AT STARTUP
    async def _run_history_update(now=None):  # <-- allow 'now' to be optional for direct call
        _LOGGER.debug("⏱️ Scheduled task: Fetching lock history diffs")

        for lock in coordinator.lock_list:
            lock_id = lock.get("lockId")
            if not lock_id:
                continue

            try:
                entries = await fetch_and_update_lock_history(coordinator, lock_id)
                if hasattr(coordinator, "update_history_sensor"):
                    await coordinator.update_history_sensor(lock_id, entries)
            except Exception as e:
                _LOGGER.warning("⚠️ Failed updating history for %s: %s", lock_id, e)

    # ⏱️ Step 3: Schedule recurring updates
    async def _run_lock_details(now):
        _LOGGER.debug("⏱️ Scheduled task: Fetching lock details")
        await coordinator.async_query_lock_details()

    async def _run_open_state(now):
        _LOGGER.debug("⏱️ Scheduled task: Fetching open/closed state")
        await coordinator.async_query_open_state()

    # 🆕 Call history update once immediately
    hass.async_create_task(_run_history_update())

    # ⏱️ Schedule repeating updates
    async_track_time_interval(hass, _run_lock_details, timedelta(seconds=DETAILS_UPDATE_INTERVAL))
    async_track_time_interval(hass, _run_open_state, timedelta(seconds=STATE_QUERY_INTERVAL))
    async_track_time_interval(hass, _run_history_update, timedelta(seconds=HISTORY_INTERVAL))

    return coordinator
