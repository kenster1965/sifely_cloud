import logging
from datetime import datetime, timezone, timedelta

from homeassistant.helpers.event import async_call_later

from .const import (
    TOKEN_ENDPOINT,
    REFRESH_ENDPOINT,
    TOKEN_REFRESH_BUFFER_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

class SifelyTokenManager:
    def __init__(self, client_id, email, password, session, hass, config_entry):
        self.client_id = client_id
        self.email = email
        self.password = password
        self.session = session
        self.hass = hass
        self.config_entry = config_entry

        self.access_token = None
        self.refresh_token_value = None
        self.token_expiry = None
        self._login_token = None

        self._refresh_unsub = None

    async def initialize(self):
        """Entry point on integration boot."""
        self._load_stored_tokens()

        if self._is_token_valid():
            _LOGGER.info("✅ Cached token found, but forcing refresh at startup.")
            await self._perform_token_refresh()
        else:
            _LOGGER.info("🔐 No valid token found. Performing login...")
            await self._perform_login()
            await self._perform_token_refresh()

    def _load_stored_tokens(self):
        opts = self.config_entry.options
        self.access_token = opts.get("access_token")
        self.refresh_token_value = opts.get("refresh_token")
        expiry_ts = opts.get("token_expiry")
        self._login_token = opts.get("login_token")

        if expiry_ts:
            self.token_expiry = datetime.fromisoformat(expiry_ts)

    def _is_token_valid(self):
        if not self.access_token or not self.token_expiry:
            return False
        return datetime.now(timezone.utc) < self.token_expiry

    async def _perform_login(self):
        _LOGGER.debug("🔐 Requesting Sifely login from: %s", TOKEN_ENDPOINT)

        try:
            async with self.session.post(TOKEN_ENDPOINT, params={
                "client_id": self.client_id,
                "username": self.email,
                "password": self.password,
            }) as resp:
                if resp.status != 200:
                    raise Exception(f"Login HTTP error: {resp.status}")

                resp_json = await resp.json(content_type=None)
                _LOGGER.debug("🔁 Login response: %s", resp_json)

                if resp_json.get("code") == 200 and "data" in resp_json:
                    data = resp_json["data"]
                    self._login_token = data.get("token")
                    self.refresh_token_value = data.get("refreshToken")
                else:
                    raise Exception(f"Login failed: {resp_json}")
        except Exception as e:
            _LOGGER.exception("🚨 Exception during login: %s", str(e))
            raise

    async def _perform_token_refresh(self):
        _LOGGER.debug("🔄 Refreshing token from: %s", REFRESH_ENDPOINT)

        try:
            async with self.session.post(REFRESH_ENDPOINT, params={
                "client_id": self.client_id,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token_value,
            }) as resp:
                if resp.status != 200:
                    raise Exception(f"Refresh HTTP error: {resp.status}")

                resp_json = await resp.json(content_type=None)
                _LOGGER.debug("🔁 Refresh token response: %s", resp_json)

                if "access_token" in resp_json:
                    self.access_token = resp_json["access_token"]
                    self.refresh_token_value = resp_json.get("refresh_token", self.refresh_token_value)
                    expires_in = resp_json.get("expires_in", 3600)
                    self._set_token_expiry(expires_in)
                    await self._store_token()
                    _LOGGER.info("🔄 Token refreshed. Expires at: %s", self.token_expiry)
                    self._schedule_token_refresh()
                else:
                    raise Exception(f"Refresh failed: {resp_json}")
        except Exception as e:
            _LOGGER.exception("🚨 Exception during token refresh: %s", str(e))
            await self._perform_login()
            await self._perform_token_refresh()

    def _set_token_expiry(self, expires_in):
        now = datetime.now(timezone.utc)
        self.token_expiry = now + timedelta(seconds=expires_in)

    def _schedule_token_refresh(self):
        if self._refresh_unsub:
            self._refresh_unsub()

        now = datetime.now(timezone.utc)
        delay = (self.token_expiry - timedelta(minutes=TOKEN_REFRESH_BUFFER_MINUTES) - now).total_seconds()
        delay = max(delay, 30)

        _LOGGER.debug("⏳ Scheduling token refresh in %.2f seconds", delay)
        self._refresh_unsub = async_call_later(self.hass, delay, self._handle_token_refresh)

    async def _handle_token_refresh(self, _):
        _LOGGER.info("🔁 Token refresh scheduled task running...")
        await self._perform_token_refresh()

    async def _store_token(self):
        opts = dict(self.config_entry.options)
        opts.update({
            "access_token": self.access_token,
            "refresh_token": self.refresh_token_value,
            "token_expiry": self.token_expiry.isoformat(),
            "login_token": self._login_token,
        })
        self.hass.config_entries.async_update_entry(self.config_entry, options=opts)

    def get_login_token(self):
        return self._login_token

    async def refresh_login_token(self):
        await self._perform_login()
        await self._perform_token_refresh()

    async def async_shutdown(self):
        if self._refresh_unsub:
            self._refresh_unsub()
            self._refresh_unsub = None
