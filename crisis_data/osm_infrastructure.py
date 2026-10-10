"""
OpenStreetMap / Overpass API Critical Infrastructure Client for CrisisOS.

This module connects to the OpenStreetMap Overpass API (https://overpass-api.de/api/interpreter)
to extract real-world critical infrastructure around Zurich, focusing on emergency facilities
(hospitals, fire stations, ambulance depots, police stations) and vulnerable transit assets (bridges).

Use Cases:
1. Identifying hospitals, medical clinics, and emergency rooms in Zurich to coordinate disaster triage.
2. Locating fire stations (Feuerwehr depots) and rescue services (Schutz & Rettung Zürich).
3. Mapping bridges crossing the Sihl and Limmat rivers to assess flood vulnerability and closure risks.
4. Caching infrastructure queries in memory to prevent exceeding Overpass API public rate limits.
"""

import time
from typing import Any, Optional
import requests

from crisis_data.config import Config
from crisis_data.logger import log_function_call, logger
from crisis_data.models import InfrastructureItem


class OverpassInfrastructureClient:
    """Client for retrieving critical emergency infrastructure from OpenStreetMap."""

    _global_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        user_agent: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> None:
        """
        Initialize the Overpass API client.

        Parameters:
            endpoint_url: Optional override for the Overpass interpreter endpoint.
            user_agent: Required HTTP User-Agent identifying the client application.
            timeout: Optional HTTP request timeout in seconds.
        """
        self.endpoint_url = endpoint_url or Config.OVERPASS_API_URL
        self.user_agent = user_agent or Config.OVERPASS_USER_AGENT
        self.timeout = timeout or Config.OVERPASS_TIMEOUT_SECONDS
        self._cache = OverpassInfrastructureClient._global_cache

    @log_function_call
    def get_nearby_infrastructure(
        self,
        latitude: float = Config.ZURICH_LAT,
        longitude: float = Config.ZURICH_LON,
        radius_km: float = 5.0,
        categories: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        """
        Query Overpass API for critical infrastructure within a radius of given coordinates.

        Parameters:
            latitude: Center latitude in WGS84 degrees (defaults to Zurich center).
            longitude: Center longitude in WGS84 degrees.
            radius_km: Search radius in kilometers (defaults to 5 km).
            categories: List of categories to query (defaults to ['hospital', 'fire_station', 'bridge']).

        Returns:
            List of normalized InfrastructureItem dictionaries.

        Raises:
            requests.RequestException: If the Overpass API is unavailable or returns an error.
        """
        target_categories = categories or ["hospital", "fire_station", "bridge"]
        radius_meters = int(radius_km * 1000)

        # Check in-memory cache
        cache_key = f"{round(latitude, 3)}_{round(longitude, 3)}_{radius_meters}_{','.join(sorted(target_categories))}"
        now = time.time()
        if cache_key in self._cache:
            timestamp, cached_items = self._cache[cache_key]
            if now - timestamp < Config.CACHE_EXPIRATION_SECONDS:
                logger.info(f"Returning {len(cached_items)} cached infrastructure items for key {cache_key}")
                return cached_items

        # Build Overpass QL query
        query_parts = []
        if "hospital" in target_categories:
            query_parts.append(f'node["amenity"="hospital"](around:{radius_meters},{latitude},{longitude});')
            query_parts.append(f'way["amenity"="hospital"](around:{radius_meters},{latitude},{longitude});')
        if "fire_station" in target_categories:
            query_parts.append(f'node["amenity"="fire_station"](around:{radius_meters},{latitude},{longitude});')
            query_parts.append(f'way["amenity"="fire_station"](around:{radius_meters},{latitude},{longitude});')
        if "bridge" in target_categories:
            query_parts.append(f'way["bridge"="yes"]["highway"](around:{radius_meters},{latitude},{longitude});')

        overpass_ql = f"""
        [out:json][timeout:{self.timeout}];
        (
          {" ".join(query_parts)}
        );
        out center tags 40;
        """

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        endpoints = [
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter",
            self.endpoint_url,
            "https://lz4.overpass-api.de/api/interpreter",
        ]
        response = None
        last_error = None
        for endpoint in endpoints:
            try:
                response = requests.post(
                    endpoint,
                    data={"data": overpass_ql},
                    headers=headers,
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    break
                else:
                    last_error = requests.HTTPError(f"{response.status_code} Error from {endpoint}")
            except requests.RequestException as exc:
                last_error = exc
                continue

        if response is None or response.status_code != 200:
            if last_error:
                raise last_error
            raise requests.RequestException("All Overpass endpoints failed")

        data = response.json()

        elements = data.get("elements", [])
        items: list[dict[str, Any]] = []

        for el in elements:
            el_type = el.get("type")
            el_id = str(el.get("id"))
            tags = el.get("tags", {})

            # Determine coordinates (nodes have lat/lon; ways with 'out center' have center: {lat, lon})
            if "lat" in el and "lon" in el:
                lat, lon = el["lat"], el["lon"]
            elif "center" in el:
                lat, lon = el["center"].get("lat"), el["center"].get("lon")
            else:
                continue

            # Classify category
            category = "unknown"
            if tags.get("amenity") == "hospital":
                category = "hospital"
            elif tags.get("amenity") == "fire_station":
                category = "fire_station"
            elif tags.get("bridge") == "yes":
                category = "bridge"

            name = tags.get("name") or tags.get("alt_name") or f"{category.capitalize()} ({el_id})"

            infra = InfrastructureItem(
                id=f"osm_{el_type}_{el_id}",
                name=name,
                category=category,
                location={"latitude": lat, "longitude": lon},
                tags={k: str(v) for k, v in tags.items() if k in ["name", "amenity", "bridge", "operator", "addr:street", "addr:city"]},
                source="OpenStreetMap",
            )
            items.append(infra.to_dict())

        # Update cache
        self._cache[cache_key] = (now, items)
        return items


# Module singleton instance
_default_overpass_client = OverpassInfrastructureClient()


@log_function_call
def get_nearby_infrastructure(
    latitude: float = Config.ZURICH_LAT,
    longitude: float = Config.ZURICH_LON,
    radius_km: float = 5.0
) -> list[dict[str, Any]]:
    """
    Convenience wrapper to retrieve critical emergency infrastructure near a coordinate.

    Parameters:
        latitude: Target latitude in WGS84 degrees.
        longitude: Target longitude in WGS84 degrees.
        radius_km: Search radius in kilometers.

    Returns:
        List of infrastructure items with coordinates and categories.
    """
    return _default_overpass_client.get_nearby_infrastructure(latitude=latitude, longitude=longitude, radius_km=radius_km)
