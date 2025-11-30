from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Dict, List

import async_timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN,
    CONF_LOCATION_ENTITY_ID,
    CONF_DISTANCE,
    DEFAULT_NAME,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def normalize_plane(p: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize ADSB.fi plane data into a simpler dict."""
    flight = (p.get("flight") or "").strip()
    return {
        "hex": p.get("hex"),
        "type": p.get("type"),
        "flight": flight or None,
        "t": p.get("t"),
        "aircraft_type": p.get("t"),
        "description": p.get("desc"),
        "category": p.get("category"),
        "lat": p.get("lat"),
        "lon": p.get("lon"),
        "alt_baro": p.get("alt_baro"),
        "ground_speed": p.get("gs"),
        "true_heading": p.get("true_heading"),
        "nav_modes": p.get("nav_modes", []),
        "on_ground": p.get("alt_baro") == "ground",
        "squawk": p.get("squawk"),
        "emergency": p.get("emergency"),
        "distance": p.get("dst"),
        "bearing": p.get("dir"),
        "seen": p.get("seen"),
        "seen_pos": p.get("seen_pos"),
        "messages": p.get("messages"),
        "rssi": p.get("rssi"),
    }


class PlanesCoordinator(DataUpdateCoordinator[List[Dict[str, Any]]]):
    """Coordinator to fetch nearby planes."""

    def __init__(
        self,
        hass: HomeAssistant,
        location_entity_id: str,
        distance: float,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="planes_nearby_coordinator",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self._location_entity_id = location_entity_id
        self._distance = distance

    async def _async_update_data(self) -> List[Dict[str, Any]]:
        """Fetch data from ADSB.fi for the current location."""
        planes: List[Dict[str, Any]] = []

        try:
            state = self.hass.states.get(self._location_entity_id)
            if not state:
                _LOGGER.error(
                    "Planes Nearby: entity %s not found", self._location_entity_id
                )
                return planes

            lat = state.attributes.get("latitude")
            lon = state.attributes.get("longitude")

            if lat is None or lon is None:
                _LOGGER.error(
                    "Planes Nearby: entity %s has no latitude/longitude",
                    self._location_entity_id,
                )
                return planes

            url = (
                f"https://opendata.adsb.fi/api/v3/lat/{lat}/lon/{lon}/dist/{self._distance}"
            )

            _LOGGER.debug("Planes Nearby: requesting ADSB.fi data from %s", url)

            session = async_get_clientsession(self.hass)

            async with async_timeout.timeout(10):
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

            raw_planes = data.get("ac", []) or []
            planes = [normalize_plane(p) for p in raw_planes]

            _LOGGER.debug("Planes Nearby: fetched %d planes", len(planes))

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Planes Nearby: error updating data: %s", err)

        return planes


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Planes Nearby sensor from a config entry."""

    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    location_entity_id = entry.options.get(
        CONF_LOCATION_ENTITY_ID,
        entry.data.get(CONF_LOCATION_ENTITY_ID),
    )
    distance = entry.options.get(
        CONF_DISTANCE,
        entry.data.get(CONF_DISTANCE, 25.0),
    )

    coordinator = PlanesCoordinator(
        hass=hass,
        location_entity_id=location_entity_id,
        distance=distance,
    )

    # If first refresh fails, we still want the entity; don't let errors bubble out
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([PlanesNearbySensor(coordinator, name)], True)


class PlanesNearbySensor(CoordinatorEntity[PlanesCoordinator], SensorEntity):
    """Sensor that exposes nearby aircraft count and details."""

    _attr_icon = "mdi:airplane"

    def __init__(self, coordinator: PlanesCoordinator, name: str) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = "planes_nearby_sensor"

    @property
    def native_value(self) -> int:
        """Return count of airborne planes (non-ground)."""
        planes = self.coordinator.data or []
        airborne = [p for p in planes if not p.get("on_ground")]
        return len(airborne)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return attributes with full plane list."""
        planes = self.coordinator.data or []
        return {
            "total_planes": len(planes),
            "planes": planes,
        }
