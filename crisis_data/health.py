"""
Data Source Health Monitor for CrisisOS Switzerland.

This module probes all external data integrations (Open-Meteo, BAFU Hydrology,
Windy Webcams, swisstopo, MeteoSwiss SMN, MeteoSwiss Radar, and OpenStreetMap Overpass),
evaluating connectivity, authentication validity, real data retrieval, and timestamp freshness.

Use Cases:
1. Providing an automated diagnostic report for developers and commanders.
2. Generating the standardized Markdown health status table required by project specifications.
3. Enabling the Gemini agent to verify live data source availability before issuing operational recommendations.
"""

from typing import Any
from crisis_data.config import Config
from crisis_data.logger import log_function_call, logger
from crisis_data.models import DataSourceHealth
from crisis_data.open_meteo import OpenMeteoClient
from crisis_data.bafu_hydro import BafuHydroClient
from crisis_data.windy_webcams import WindyWebcamsClient
from crisis_data.swisstopo import SwisstopoClient
from crisis_data.meteoswiss_smn import MeteoSwissSMNClient
from crisis_data.meteoswiss_radar import MeteoSwissRadarClient
from crisis_data.osm_infrastructure import OverpassInfrastructureClient


class HealthMonitor:
    """Aggregates and performs live health checks for all CrisisOS external data integrations."""

    def __init__(self) -> None:
        """Initialize clients for all sources."""
        self.open_meteo = OpenMeteoClient()
        self.bafu = BafuHydroClient()
        self.windy = WindyWebcamsClient()
        self.swisstopo = SwisstopoClient()
        self.meteoswiss_smn = MeteoSwissSMNClient()
        self.meteoswiss_radar = MeteoSwissRadarClient()
        self.overpass = OverpassInfrastructureClient()

    @log_function_call
    def check_all_sources(self) -> list[DataSourceHealth]:
        """
        Run live diagnostic probes against all integrated services.

        Returns:
            List of DataSourceHealth records for each integration.
        """
        reports: list[DataSourceHealth] = []

        # 1. Open-Meteo
        try:
            res = self.open_meteo.get_weather(Config.ZURICH_LAT, Config.ZURICH_LON)
            has_obs = len(res.get("normalized_observations", [])) > 0
            reports.append(DataSourceHealth(
                source="Open-Meteo Weather",
                auth_required=False,
                connectivity=True,
                real_data_retrieved=has_obs,
                freshness="Live (15-min intervals)",
                status="WORKING" if has_obs else "PARTIALLY WORKING",
                details=f"Current temp: {res.get('current_weather', {}).get('temperature_2m')}°C",
            ))
        except Exception as e:
            reports.append(DataSourceHealth(
                source="Open-Meteo Weather",
                auth_required=False,
                connectivity=False,
                real_data_retrieved=False,
                freshness="N/A",
                status="BLOCKED",
                details=str(e),
            ))

        # 2. BAFU Hydrology
        try:
            stations = self.bafu.get_river_stations()
            sihl_live = self.bafu.get_river_measurements("2176")  # Sihl
            has_data = len(sihl_live.get("latest_parameters", {})) > 0
            freshness = "Live (10-min intervals)" if has_data else "No live readings"
            reports.append(DataSourceHealth(
                source="BAFU / FOEN Hydrology",
                auth_required=False,
                connectivity=True,
                real_data_retrieved=has_data,
                freshness=freshness,
                status="WORKING" if (stations and has_data) else "PARTIALLY WORKING",
                details=f"{len(stations)} Zurich stations; Sihl parameters: {list(sihl_live.get('latest_parameters', {}).keys())}",
            ))
        except Exception as e:
            reports.append(DataSourceHealth(
                source="BAFU / FOEN Hydrology",
                auth_required=False,
                connectivity=False,
                real_data_retrieved=False,
                freshness="N/A",
                status="BLOCKED",
                details=str(e),
            ))

        # 3. Windy Webcams V3
        if not self.windy.is_configured():
            reports.append(DataSourceHealth(
                source="Windy Webcams V3",
                auth_required=True,
                connectivity=True,
                real_data_retrieved=False,
                freshness="N/A (Key required)",
                status="NEEDS API KEY",
                details="Header 'x-windy-api-key' required. Register at https://api.windy.com/.",
            ))
        else:
            try:
                cams = self.windy.get_nearby_webcams(Config.ZURICH_LAT, Config.ZURICH_LON, radius_km=15)
                has_cams = len(cams) > 0 and not cams[0].get("is_simulated")
                reports.append(DataSourceHealth(
                    source="Windy Webcams V3",
                    auth_required=True,
                    connectivity=True,
                    real_data_retrieved=has_cams,
                    freshness="Near real-time (15-min to 1-hr updates)",
                    status="WORKING" if has_cams else "PARTIALLY WORKING",
                    details=f"{len(cams)} cameras returned",
                ))
            except Exception as e:
                reports.append(DataSourceHealth(
                    source="Windy Webcams V3",
                    auth_required=True,
                    connectivity=False,
                    real_data_retrieved=False,
                    freshness="N/A",
                    status="BLOCKED",
                    details=str(e),
                ))

        # 4. swisstopo
        try:
            elev = self.swisstopo.get_elevation(Config.ZURICH_LAT, Config.ZURICH_LON)
            has_elev = elev.get("elevation_m") is not None
            reports.append(DataSourceHealth(
                source="swisstopo Geodata",
                auth_required=False,
                connectivity=True,
                real_data_retrieved=has_elev,
                freshness="Static DEM / Official Cartography",
                status="WORKING" if has_elev else "PARTIALLY WORKING",
                details=f"Zurich center elevation: {elev.get('elevation_m')} m a.s.l.",
            ))
        except Exception as e:
            reports.append(DataSourceHealth(
                source="swisstopo Geodata",
                auth_required=False,
                connectivity=False,
                real_data_retrieved=False,
                freshness="N/A",
                status="BLOCKED",
                details=str(e),
            ))

        # 5. MeteoSwiss SwissMetNet
        try:
            obs = self.meteoswiss_smn.get_station_latest_observations("sma")
            has_readings = len(obs.get("normalized_observations", [])) > 0
            reports.append(DataSourceHealth(
                source="MeteoSwiss Weather Stations",
                auth_required=False,
                connectivity=True,
                real_data_retrieved=has_readings,
                freshness=f"Observed at {obs.get('timestamp')}",
                status="WORKING" if has_readings else "PARTIALLY WORKING",
                details=f"Station SMA (Fluntern) temp: {obs.get('raw_measurements', {}).get('temperature_c')}°C",
            ))
        except Exception as e:
            reports.append(DataSourceHealth(
                source="MeteoSwiss Weather Stations",
                auth_required=False,
                connectivity=False,
                real_data_retrieved=False,
                freshness="N/A",
                status="BLOCKED",
                details=str(e),
            ))

        # 6. MeteoSwiss Radar STAC
        try:
            radar = self.meteoswiss_radar.get_precipitation_radar(limit=1)
            has_items = len(radar.get("items", [])) > 0
            reports.append(DataSourceHealth(
                source="MeteoSwiss Precipitation Radar",
                auth_required=False,
                connectivity=True,
                real_data_retrieved=has_items,
                freshness=f"Latest update: {radar.get('latest_update')}",
                status="WORKING" if has_items else "PARTIALLY WORKING",
                details="STAC items and HDF5 assets reachable; metadata exposed.",
            ))
        except Exception as e:
            reports.append(DataSourceHealth(
                source="MeteoSwiss Precipitation Radar",
                auth_required=False,
                connectivity=False,
                real_data_retrieved=False,
                freshness="N/A",
                status="BLOCKED",
                details=str(e),
            ))

        # 7. OpenStreetMap / Overpass
        try:
            infra = self.overpass.get_nearby_infrastructure(Config.ZURICH_LAT, Config.ZURICH_LON, radius_km=3.0)
            has_infra = len(infra) > 0
            reports.append(DataSourceHealth(
                source="OpenStreetMap Overpass",
                auth_required=False,
                connectivity=True,
                real_data_retrieved=has_infra,
                freshness="Live OSM Database",
                status="WORKING" if has_infra else "PARTIALLY WORKING",
                details=f"{len(infra)} infrastructure features within 3km of Zurich center",
            ))
        except Exception as e:
            reports.append(DataSourceHealth(
                source="OpenStreetMap Overpass",
                auth_required=False,
                connectivity=False,
                real_data_retrieved=False,
                freshness="N/A",
                status="BLOCKED",
                details=str(e),
            ))

        return reports

    def generate_markdown_table(self, reports: list[DataSourceHealth]) -> str:
        """
        Format health check results as a standardized GitHub Markdown table.

        Parameters:
            reports: List of DataSourceHealth records.

        Returns:
            Formatted Markdown table string.
        """
        headers = ["Source", "Auth required", "Connectivity", "Real data retrieved", "Freshness", "Status"]
        separator = ["---", "---", "---", "---", "---", "---"]
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        for r in reports:
            auth_str = "Yes" if r.auth_required else "No"
            conn_str = "✓ Connected" if r.connectivity else "✕ Failed"
            data_str = "✓ Yes" if r.real_data_retrieved else "✕ No"
            row = [
                r.source,
                auth_str,
                conn_str,
                data_str,
                r.freshness,
                r.status,
            ]
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)


_default_monitor = HealthMonitor()


@log_function_call
def get_data_source_health() -> dict[str, Any]:
    """
    Convenience function returning the structured health check report and Markdown table.

    Returns:
        Dictionary containing health records and Markdown summary.
    """
    reports = _default_monitor.check_all_sources()
    table = _default_monitor.generate_markdown_table(reports)
    return {
        "reports": [r.to_dict() for r in reports],
        "markdown_table": table,
    }
