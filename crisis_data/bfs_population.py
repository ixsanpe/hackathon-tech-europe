"""
Swiss Population and Building Exposure (BFS) Integration for CrisisOS Switzerland.

This module accesses official Swiss Federal Statistical Office (Bundesamt für Statistik, BFS)
data sources, primarily the Federal Register of Buildings and Dwellings (Eidg. Gebäude- und
Wohnungsregister, GWR: `ch.bfs.gebaeude_wohnungs_register`) and municipal population statistics (STATPOP).

During flood or earthquake crises in Zurich, emergency coordinators must determine not only where
hazards exist, but what human populations and physical structures are exposed. This module enables
CrisisOS to identify building inventories (construction epoch, number of storeys, surface footprint)
and municipal population density within flood-vulnerable postal sectors.

Use Cases:
1. Querying official building registers in Zurich postal zones (e.g. 8001 Altstadt, 8005 Industriequartier).
2. Assessing vulnerability profiles based on building construction years, residential floors, and surface areas.
3. Calculating exposed population density metrics for emergency evacuations.
4. Supplying building inventory exposure data to the Gemini multimodal agent.
"""

from typing import Any, Optional
import requests

from crisis_data.config import Config
from crisis_data.logger import log_function_call, logger
from crisis_data.models import BuildingExposureInfo
from crisis_data.swisstopo import lv95_to_wgs84


class BfsPopulationClient:
    """Client for querying BFS building registers and population density metrics."""

    def __init__(self, timeout_seconds: Optional[int] = None) -> None:
        """
        Initialize the BFS population and building client.

        Args:
            timeout_seconds: Network request timeout in seconds.
        """
        self.timeout: int = timeout_seconds or Config.BFS_TIMEOUT_SECONDS
        self.search_url: str = Config.BFS_GWR_SEARCH_URL
        self.gwr_layer: str = Config.BFS_GWR_LAYER

    @log_function_call
    def get_building_exposure(
        self,
        postal_code: int = 8001,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """
        Retrieve official building records from the BFS GWR for a given postal code.

        Args:
            postal_code: 4-digit Swiss postal code (e.g. 8001, 8005, 8002).
            limit: Maximum number of building records to return.

        Returns:
            List of normalized building exposure dictionaries.
        """
        params = {
            "layer": self.gwr_layer,
            "searchText": str(postal_code),
            "searchField": "dplz4",
            "returnGeometry": "false",
        }

        buildings: list[dict[str, Any]] = []
        try:
            response = requests.get(
                self.search_url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])

            for res in results[:limit]:
                attrs = res.get("attributes", {})
                egid = str(attrs.get("egid") or "")
                street = attrs.get("strname_deinr") or attrs.get("label") or "Unknown Street"
                house_no = attrs.get("deinr") or ""
                plz = int(attrs.get("dplz4") or postal_code)
                commune = attrs.get("ggdename") or "Zürich"
                year_built = attrs.get("gbauj")
                floors = attrs.get("gastw")
                area_m2 = attrs.get("garea")

                # Coordinates in LV95 (gkode, gkodn)
                east = attrs.get("gkode")
                north = attrs.get("gkodn")
                lat, lon = None, None
                if east and north:
                    try:
                        lat, lon = lv95_to_wgs84(float(east), float(north))
                        lat = round(lat, 5)
                        lon = round(lon, 5)
                    except Exception as ce:
                        logger.debug(f"Coordinate conversion error for EGID {egid}: {ce}")

                building = BuildingExposureInfo(
                    egid=egid,
                    street=street,
                    house_number=str(house_no),
                    postal_code=plz,
                    municipality=commune,
                    year_built=int(year_built) if year_built else None,
                    floors=int(floors) if floors else None,
                    area_m2=float(area_m2) if area_m2 else None,
                    latitude=lat,
                    longitude=lon,
                    population_density_km2=Config.BFS_ZURICH_DENSITY_PER_KM2,
                    source="BFS_GWR",
                )
                buildings.append(building.to_dict())

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to query BFS building register for PLZ {postal_code}: {e}")

        return buildings

    @log_function_call
    def get_population_exposure_metrics(self, postal_code: int = 8001) -> dict[str, Any]:
        """
        Compute an aggregated exposure and demographic profile for a Zurich postal sector.

        Args:
            postal_code: 4-digit Swiss postal code.

        Returns:
            Dictionary containing population estimates, building statistics, and vulnerability summary.
        """
        buildings = self.get_building_exposure(postal_code=postal_code, limit=50)

        # Calculate metrics
        buildings_count = len(buildings)
        avg_floors = 0.0
        floors_list = [b["floors"] for b in buildings if b["floors"] is not None]
        if floors_list:
            avg_floors = round(sum(floors_list) / len(floors_list), 1)

        historic_buildings = len([b for b in buildings if b["year_built"] and b["year_built"] < 1950])

        return {
            "postal_code": postal_code,
            "municipality": "Zürich",
            "canton": "ZH",
            "total_municipality_population": Config.BFS_ZURICH_POPULATION_ESTIMATE,
            "municipality_area_km2": Config.BFS_ZURICH_AREA_KM2,
            "population_density_per_km2": Config.BFS_ZURICH_DENSITY_PER_KM2,
            "sample_buildings_analyzed": buildings_count,
            "average_building_floors": avg_floors,
            "historic_buildings_pre_1950": historic_buildings,
            "statpop_map_url": "https://map.geo.admin.ch/?layers=ch.bfs.volkszaehlung-bevoelkerungsstatistik_einwohner",
            "sample_buildings": buildings[:5],
            "source": "BFS_STATPOP_GWR",
        }


# Default client instance
_default_bfs_client = BfsPopulationClient()


@log_function_call
def get_building_exposure(
    postal_code: int = 8001,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """
    Public entry point to retrieve building register records for an area.

    Args:
        postal_code: 4-digit postal code (default: 8001).
        limit: Maximum number of building records.

    Returns:
        List of normalized building records.
    """
    return _default_bfs_client.get_building_exposure(
        postal_code=postal_code,
        limit=limit,
    )


@log_function_call
def get_population_exposure_metrics(postal_code: int = 8001) -> dict[str, Any]:
    """
    Public entry point to generate demographic and building exposure metrics.

    Args:
        postal_code: 4-digit postal code.

    Returns:
        Demographic and infrastructure exposure summary dictionary.
    """
    return _default_bfs_client.get_population_exposure_metrics(postal_code=postal_code)
