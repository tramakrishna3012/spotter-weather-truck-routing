"""Weather forecast provider adapters (Open-Meteo live and deterministic fixture)."""

from providers.weather.fixture_adapter import FixtureWeatherProvider
from providers.weather.open_meteo_adapter import OpenMeteoWeatherProvider

__all__ = [
    "FixtureWeatherProvider",
    "OpenMeteoWeatherProvider",
]
