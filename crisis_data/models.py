"""
Normalized Data Models for CrisisOS Switzerland.

This module defines standard data structures and schemas used across all CrisisOS data integrations.
Normalizing incoming data from disparate providers (Open-Meteo, BAFU GraphQL, swisstopo, MeteoSwiss,
Windy, and OpenStreetMap) into a uniform schema allows the Gemini reasoning agent and downstream
services to process environmental, hydrological, and infrastructure information seamlessly.

Use Cases:
1. Normalizing river gauge observations (water level, discharge) into standard SI/metric units.
2. Structuring weather and precipitation readings with explicit timestamps and freshness indicators.
3. Modeling public camera feeds (images, coordinates, update timestamps) for multimodal Gemini ingestion.
4. Encapsulating infrastructure features (hospitals, fire stations, bridges) around Zurich.
5. Standardizing health check reporting across all integrated data providers.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def current_utc_iso() -> str:
    """
    Generate the current UTC timestamp formatted as an ISO-8601 string.

    Returns:
        ISO-8601 formatted timestamp in UTC.
    """
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GeoLocation:
    """Geographic point representation in standard WGS84 coordinates."""
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert location to a dictionary."""
        d = {"latitude": self.latitude, "longitude": self.longitude}
        if self.elevation_m is not None:
            d["elevation_m"] = self.elevation_m
        return d


@dataclass
class NormalizedObservation:
    """
    Normalized environmental or hydrological observation record.

    Follows the CrisisOS standard schema required for Gemini decision-making.
    """
    source: str
    type: str
    station_id: str
    location: Optional[dict[str, Any]]
    measurement: dict[str, Any]
    observed_at: str
    retrieved_at: str = field(default_factory=current_utc_iso)
    is_simulated: bool = False
    quality: str = "nominal"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the normalized observation to a clean dictionary."""
        return asdict(self)


@dataclass
class CameraMetadata:
    """Metadata describing a public monitoring webcam."""
    camera_id: str
    title: str
    location: Optional[dict[str, Any]]
    image_url: Optional[str]
    preview_url: Optional[str]
    updated_at: Optional[str]
    status: str
    source: str = "Windy"
    is_simulated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert camera metadata to dictionary."""
        return asdict(self)


@dataclass
class InfrastructureItem:
    """Critical or emergency infrastructure feature extracted from OpenStreetMap."""
    id: str
    name: str
    category: str  # e.g., 'hospital', 'fire_station', 'bridge'
    location: dict[str, float]
    tags: dict[str, str] = field(default_factory=dict)
    source: str = "OpenStreetMap"

    def to_dict(self) -> dict[str, Any]:
        """Convert infrastructure item to dictionary."""
        return asdict(self)


@dataclass
class DataSourceHealth:
    """Health check outcome for an external data source."""
    source: str
    auth_required: bool
    connectivity: bool
    real_data_retrieved: bool
    freshness: str
    status: str  # 'WORKING', 'PARTIALLY WORKING', 'NEEDS API KEY', 'BLOCKED', 'NOT IMPLEMENTED'
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert health record to dictionary."""
        return asdict(self)
