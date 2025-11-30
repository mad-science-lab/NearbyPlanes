from __future__ import annotations

from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_LOCATION_ENTITY_ID,
    CONF_DISTANCE,
    DEFAULT_NAME,
)


class InvalidLocationEntity(HomeAssistantError):
    """Error raised when the location entity is invalid."""


def _validate_location_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Validate that the entity exists and has latitude/longitude."""
    state = hass.states.get(entity_id)
    if not state:
        raise InvalidLocationEntity(f"Entity {entity_id} not found")

    attrs = state.attributes or {}
    if "latitude" not in attrs or "longitude" not in attrs:
        raise InvalidLocationEntity(
            f"Entity {entity_id} has no latitude/longitude attributes"
        )


class PlanesNearbyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Planes Nearby."""

    VERSION = 1

    def __init__(self) -> None:
        self._errors: Dict[str, str] = {}

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle the initial step."""
        self._errors = {}

        if user_input is not None:
            name = user_input.get(CONF_NAME) or DEFAULT_NAME
            location_entity_id = user_input[CONF_LOCATION_ENTITY_ID]
            distance = user_input[CONF_DISTANCE]

            try:
                _validate_location_entity(self.hass, location_entity_id)
            except InvalidLocationEntity:
                self._errors["base"] = "invalid_entity"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_LOCATION_ENTITY_ID: location_entity_id,
                        CONF_DISTANCE: distance,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_LOCATION_ENTITY_ID): str,
                vol.Required(CONF_DISTANCE, default=25.0): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=self._errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        # Home Assistant will set self.config_entry on the options flow
        return PlanesNearbyOptionsFlowHandler()



class PlanesNearbyOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Planes Nearby."""

    def __init__(self) -> None:
        """Initialize options flow."""
        # self.config_entry is now provided by the parent class
        self._errors: Dict[str, str] = {}


    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Manage the options."""
        self._errors = {}

        if user_input is not None:
            location_entity_id = user_input[CONF_LOCATION_ENTITY_ID]
            distance = user_input[CONF_DISTANCE]

            try:
                _validate_location_entity(self.hass, location_entity_id)
            except InvalidLocationEntity:
                self._errors["base"] = "invalid_entity"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_LOCATION_ENTITY_ID: location_entity_id,
                        CONF_DISTANCE: distance,
                    },
                )

        current_location = (
            self.config_entry.options.get(CONF_LOCATION_ENTITY_ID)
            or self.config_entry.data.get(CONF_LOCATION_ENTITY_ID)
            or ""
        )
        current_distance = (
            self.config_entry.options.get(CONF_DISTANCE)
            or self.config_entry.data.get(CONF_DISTANCE)
            or 25.0
        )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOCATION_ENTITY_ID, default=current_location
                ): str,
                vol.Required(CONF_DISTANCE, default=current_distance): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=self._errors
        )
