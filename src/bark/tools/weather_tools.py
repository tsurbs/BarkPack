"""Weather tool using the Open-Meteo free API."""

import logging

import httpx

from bark.core.tools import tool

logger = logging.getLogger(__name__)

# WMO Weather interpretation codes
# https://open-meteo.com/en/docs#weathervariables
_WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _c_to_f(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return celsius * 9.0 / 5.0 + 32.0


def _describe_weather_code(code: int) -> str:
    """Map a WMO weather code to a human-readable condition string."""
    return _WEATHER_CODES.get(code, f"Unknown (code {code})")


@tool(
    name="get_weather",
    description=(
        "Get current weather conditions for a city. "
        "Returns temperature in °F, wind speed, and a human-readable condition. "
        "Uses the free Open-Meteo API (no key required)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City name to look up, e.g. 'Pittsburgh' or 'Tokyo, Japan'",
            },
        },
        "required": ["location"],
    },
)
async def get_weather(location: str) -> str:
    """Geocode a city name and return its current weather conditions."""
    async with httpx.AsyncClient(timeout=15) as client:
        # --- Step 1: Geocode the location ---
        try:
            geo_resp = await client.get(
                _GEOCODING_URL,
                params={"name": location, "count": 1, "language": "en", "format": "json"},
            )
            geo_resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("Geocoding HTTP error for %s: %s", location, e)
            return f"❌ Geocoding API error (HTTP {e.response.status_code}). Please try again."
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error("Geocoding network error for %s: %s", location, e)
            return "❌ Could not reach the geocoding service. Please try again later."

        geo_data = geo_resp.json()
        results = geo_data.get("results")
        if not results:
            return f"❌ Could not find a location matching **{location}**. Try a different spelling or add a country name."

        place = results[0]
        lat = place["latitude"]
        lon = place["longitude"]
        name = place.get("name", location)
        country = place.get("country", "")
        display_name = f"{name}, {country}" if country else name

        # --- Step 2: Fetch current weather ---
        try:
            wx_resp = await client.get(
                _FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,wind_speed_10m,weather_code",
                },
            )
            wx_resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("Forecast HTTP error for %s: %s", display_name, e)
            return f"❌ Weather API error (HTTP {e.response.status_code}). Please try again."
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error("Forecast network error for %s: %s", display_name, e)
            return "❌ Could not reach the weather service. Please try again later."

        wx_data = wx_resp.json()
        current = wx_data.get("current")
        if not current:
            return f"❌ No current weather data available for **{display_name}**."

        temp_c = current.get("temperature_2m")
        wind_speed = current.get("wind_speed_10m")
        weather_code = current.get("weather_code")

        if temp_c is None:
            return f"❌ Incomplete weather data for **{display_name}**."

        temp_f = _c_to_f(temp_c)
        condition = _describe_weather_code(weather_code) if weather_code is not None else "Unknown"
        wind_str = f"{wind_speed} km/h" if wind_speed is not None else "N/A"

        return (
            f"🌤️ **Weather for {display_name}**\n"
            f"• **Temperature:** {temp_f:.1f} °F ({temp_c:.1f} °C)\n"
            f"• **Condition:** {condition}\n"
            f"• **Wind speed:** {wind_str}"
        )
