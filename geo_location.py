from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_LOCATION_ENTITY_ID,
    CONF_DISTANCE,
)
from .sensor import PlanesCoordinator, normalize_plane  # reuse logic

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up geo_location entities for planes from a config entry."""

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

    await coordinator.async_config_entry_first_refresh()

    entities: List[PlaneGeoLocation] = []

    def _update_entities() -> None:
        """Create new entities for new planes based on hex."""
        existing_hexes = {e.hex_id for e in entities}
        new_entities: List[PlaneGeoLocation] = []

        for plane in coordinator.data or []:
            hex_id = plane.get("hex")
            if not hex_id or hex_id in existing_hexes:
                continue
            new_entity = PlaneGeoLocation(coordinator, hex_id)
            new_entities.append(new_entity)
            existing_hexes.add(hex_id)

        if new_entities:
            entities.extend(new_entities)
            async_add_entities(new_entities)

    # Initial entity set
    _update_entities()
    # Add more entities dynamically as new planes appear
    coordinator.async_add_listener(_update_entities)


class PlaneGeoLocation(CoordinatorEntity[PlanesCoordinator], GeolocationEvent):
    """Geo-location entity for a single plane."""

    def __init__(self, coordinator: PlanesCoordinator, hex_id: str) -> None:
        super().__init__(coordinator)
        self.hex_id = hex_id
        self._attr_unique_id = f"planes_nearby_{hex_id}"
        self._attr_icon = "mdi:airplane"

    def _plane(self) -> Optional[Dict[str, Any]]:
        """Return the plane dict for this hex."""
        for p in self.coordinator.data or []:
            if p.get("hex") == self.hex_id:
                return p
        return None

    @property
    def available(self) -> bool:
        """Entity is available only while the plane is in the coordinator data."""
        return self._plane() is not None

    @property
    def latitude(self) -> float | None:
        plane = self._plane()
        return plane.get("lat") if plane else None

    @property
    def longitude(self) -> float | None:
        plane = self._plane()
        return plane.get("lon") if plane else None

    @property
    def source(self) -> str:
        """Source label shown in some map views."""
        return DOMAIN

    @property
    def name(self) -> str:
        plane = self._plane()
        if not plane:
            return f"Plane {self.hex_id}"
        flight = (plane.get("flight") or "").strip()
        if flight:
            return f"{flight} ({self.hex_id})"
        return f"Plane {self.hex_id}"

    @property
    def state(self) -> Any:
        """Use distance as 'state'."""
        plane = self._plane()
        if not plane:
            return None
        return plane.get("distance")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        plane = self._plane() or {}
        return {
            "hex": plane.get("hex"),
            "flight": plane.get("flight"),
            "t": plane.get("t"),
            "alt_baro": plane.get("alt_baro"),
            "true_heading": plane.get("true_heading"),
            "nav_modes": plane.get("nav_modes", []),
            "distance": plane.get("distance"),
            "on_ground": plane.get("on_ground"),
            "rssi": plane.get("rssi"),
        }
