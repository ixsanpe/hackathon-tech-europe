"""
Centralized Configuration Module for CrisisOS Switzerland Data Integration.

This module consolidates all application configurations, endpoint definitions,
default coordinates, timeouts, and environment variable loaders in one centralized location.
By gathering all settings here, the application avoids hardcoded constants across different
modules and enables uniform environment variable management.

Use Cases:
1. Loading and validating environment variables (e.g., API keys for Windy Webcams, Gemini API).
2. Supplying default coordinates, bounding boxes, and radii for Zurich and Swiss water bodies (Limmat, Sihl).
3. Defining standard HTTP timeouts, user agents, and retry thresholds across all integration clients.
4. Centralizing model names and GenAI configurations for the Gemini reasoning agent.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load local .env file if available
load_dotenv()


class Config:
    """Central configuration class holding all constants, endpoints, and credentials."""

    # --------------------------------------------------------------------------
    # Geographic Focus: Zurich & Switzerland
    # --------------------------------------------------------------------------
    ZURICH_LAT: float = 47.3769
    ZURICH_LON: float = 8.5417
    DEFAULT_RADIUS_KM: float = 15.0

    # Bounding box for Zurich metro area [south_lat, west_lon, north_lat, east_lon]
    ZURICH_BBOX: dict[str, float] = {
        "min_lat": 47.3200,
        "min_lon": 8.4500,
        "max_lat": 47.4500,
        "max_lon": 8.6200,
    }

    # --------------------------------------------------------------------------
    # Priority 1: Open-Meteo Weather API
    # --------------------------------------------------------------------------
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPEN_METEO_TIMEOUT_SECONDS: int = 10

    # --------------------------------------------------------------------------
    # Priority 2: BAFU / FOEN Hydrology GraphQL
    # --------------------------------------------------------------------------
    BAFU_GRAPHQL_URL: str = "https://data.bafu.admin.ch/api"
    BAFU_TIMEOUT_SECONDS: int = 15
    # Key stations near Zurich:
    # 2176: Zürich, Sihlhölzli (River Sihl)
    # 2099: Zürich, Unterhard (River Limmat)
    # 2209: Zürich (Zürichsee)
    # 2243: Baden, Limmatpromenade (River Limmat downstream)
    BAFU_PRIMARY_ZURICH_STATIONS: list[str] = ["2176", "2099", "2209", "2243"]

    # --------------------------------------------------------------------------
    # Priority 3: Windy Webcams API V3
    # --------------------------------------------------------------------------
    WINDY_WEBCAMS_BASE_URL: str = "https://api.windy.com/webcams/api/v3/webcams"
    WINDY_TIMEOUT_SECONDS: int = 10
    WINDY_API_KEY: Optional[str] = os.getenv("WINDY_API_KEY") or os.getenv("WINDY_WEBCAM_API_KEY") or os.getenv("WINDY_WEBCAMS_API_KEY")

    # --------------------------------------------------------------------------
    # Priority 4: swisstopo / Swiss Federal Geodata
    # --------------------------------------------------------------------------
    SWISSTOPO_STAC_BASE_URL: str = "https://data.geo.admin.ch/api/stac/v1"
    SWISSTOPO_REST_BASE_URL: str = "https://api3.geo.admin.ch/rest/services"
    SWISSTOPO_HEIGHT_URL: str = "https://api3.geo.admin.ch/rest/services/height"
    SWISSTOPO_GEODESY_URL: str = "https://geodesy.geo.admin.ch/reframe"
    SWISSTOPO_TIMEOUT_SECONDS: int = 10

    # --------------------------------------------------------------------------
    # Priority 5: MeteoSwiss Weather Stations (SwissMetNet)
    # --------------------------------------------------------------------------
    METEOSWISS_SMN_STAC_URL: str = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-smn"
    METEOSWISS_SMN_ASSET_BASE: str = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn"
    METEOSWISS_SMN_TIMEOUT_SECONDS: int = 15
    METEOSWISS_DEFAULT_STATION: str = "sma"  # Zürich / Fluntern

    # --------------------------------------------------------------------------
    # Priority 6: MeteoSwiss Precipitation Radar
    # --------------------------------------------------------------------------
    METEOSWISS_RADAR_STAC_URL: str = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-radar-precip"
    METEOSWISS_RADAR_TIMEOUT_SECONDS: int = 15

    # --------------------------------------------------------------------------
    # Priority 7: OpenStreetMap / Overpass API
    # --------------------------------------------------------------------------
    OVERPASS_API_URL: str = "https://overpass-api.de/api/interpreter"
    OVERPASS_USER_AGENT: str = "CrisisOS-Zurich/1.0 (hackathon-emergency-agent; https://github.com/ixsanpe/hackathon-tech-europe)"
    OVERPASS_TIMEOUT_SECONDS: int = 25

    # --------------------------------------------------------------------------
    # Gemini / GenAI Configuration
    # --------------------------------------------------------------------------
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    GEMINI_DEFAULT_MODEL: str = "gemini-2.5-flash"
    GEMINI_VISION_MODEL: str = "gemini-2.5-flash"
    GEMINI_REASONING_MODEL: str = "gemini-2.5-pro"

    # --------------------------------------------------------------------------
    # General HTTP & Cache Settings
    # --------------------------------------------------------------------------
    HTTP_MAX_RETRIES: int = 2
    HTTP_BACKOFF_FACTOR: float = 0.5
    CACHE_EXPIRATION_SECONDS: int = 180  # 3 minutes default memory cache


def get_config() -> type[Config]:
    """
    Return the global Config class.

    Returns:
        The Config class containing all environment and operational constants.
    """
    return Config
