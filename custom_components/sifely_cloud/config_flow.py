import logging
import aiohttp
import hashlib
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_CLIENT_ID,
    CONF_APX_NUM_LOCKS,
    CONF_HISTORY_ENTRIES,
    LOGIN_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


class SifelyCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sifely Cloud along with finding client_id."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            raw_password = user_input[CONF_PASSWORD]
            md5_password = hashlib.md5(raw_password.encode()).hexdigest()
            _LOGGER.debug("🔐 Attempting login with email: %s", email, " | MD5: %s", md5_password)
            
            # Attempt to fetch client_id from Sifely using username and password
            try:
                async with aiohttp.ClientSession() as session:
                    data = {"username": email, "password": md5_password}
                    header = {"Content-Type": "application/x-www-form-urlencoded"}
                    async with session.post(
                        LOGIN_ENDPOINT,
                        headers=header,
                        data = data
                    ) as response:
                        _LOGGER.debug("Sifely login response: %s", response)
                        if response.status == 500:
                            errors["base"] = "bad_username"
                            return await self._show_form(user_input, errors)
                        elif response.status == 401:
                            errors["base"] = "bad_password"
                            return await self._show_form(user_input, errors)
                        elif response.status != 200:
                            errors["base"] = "unknown_error"
                            return await self._show_form(user_input, errors)

                        data = await response.json()
                        client_id = data["data"]["clientId"]

            except Exception as e:
                _LOGGER.exception("Error during login request: %s", e)
                errors["base"] = "connection_error"
                return await self._show_form(user_input, errors)

            # Store clientId in options
            return self.async_create_entry(
                title=email,
                data={},
                options={
                    CONF_EMAIL: email,
                    CONF_PASSWORD: raw_password,
                    CONF_CLIENT_ID: client_id,
                    CONF_APX_NUM_LOCKS: user_input[CONF_APX_NUM_LOCKS],
                    CONF_HISTORY_ENTRIES: user_input.get(CONF_HISTORY_ENTRIES, 20),
                },
            )
        return await self._show_form(user_input={}, errors=errors)


    async def _show_form(self, user_input, errors) -> FlowResult:
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL, default=user_input.get(CONF_EMAIL, "")): str,
                vol.Required(CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")): str,
                vol.Required(CONF_APX_NUM_LOCKS, default=user_input.get(CONF_APX_NUM_LOCKS, 5)): vol.In([5, 10, 15, 20, 25, 30, 35, 40, 45, 50]),
                vol.Required(CONF_HISTORY_ENTRIES, default=user_input.get(CONF_HISTORY_ENTRIES, 20)): vol.In([10, 20, 30, 40, 50, 60, 70, 80, 90, 100]),
            }),
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Expose the options flow handler for the gear icon."""
        return SifelyCloudOptionsFlowHandler(config_entry)


class SifelyCloudOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Sifely Cloud."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Initial step for options flow (gear icon)."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None) -> FlowResult:
        _LOGGER.debug("⚙️ OptionsFlow triggered with current options: %s", self.config_entry.options)

        def default(key, fallback=""):
            return self.config_entry.options.get(key, self.config_entry.data.get(key, fallback))

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL, default=default(CONF_EMAIL)): str,
                vol.Required(CONF_PASSWORD, default=default(CONF_PASSWORD)): str,
                vol.Required(CONF_CLIENT_ID, default=default(CONF_CLIENT_ID)): str,
                vol.Required(CONF_APX_NUM_LOCKS, default=default(CONF_APX_NUM_LOCKS, '5' )): vol.In([5, 10, 15, 20, 25, 30, 35, 40, 45, 50]),
                vol.Required(CONF_HISTORY_ENTRIES, default=default(CONF_HISTORY_ENTRIES, '20')): vol.In([10, 20, 30, 40, 50, 60, 70, 80, 90, 100]),
            }),
        )
