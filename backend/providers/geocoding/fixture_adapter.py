"""Deterministic fixture geocoding provider covering major US freight hubs and disambiguation."""

from __future__ import annotations

import math
import re

from providers.ports import GeoLocation

_COORD_PAIR_RE = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*$"
)

_FIXTURE_HUBS: tuple[GeoLocation, ...] = (
    GeoLocation(
        label="New York, NY",
        latitude=40.7128,
        longitude=-74.0060,
        provider_id="fixture:nyc-ny",
        country_code="USA",
        region="NY",
        locality="New York",
        confidence=1.0,
    ),
    GeoLocation(
        label="Philadelphia, PA",
        latitude=39.9526,
        longitude=-75.1652,
        provider_id="fixture:phl-pa",
        country_code="USA",
        region="PA",
        locality="Philadelphia",
        confidence=1.0,
    ),
    GeoLocation(
        label="Chicago, IL",
        latitude=41.8781,
        longitude=-87.6298,
        provider_id="fixture:chi-il",
        country_code="USA",
        region="IL",
        locality="Chicago",
        confidence=1.0,
    ),
    GeoLocation(
        label="Detroit, MI",
        latitude=42.3314,
        longitude=-83.0458,
        provider_id="fixture:det-mi",
        country_code="USA",
        region="MI",
        locality="Detroit",
        confidence=1.0,
    ),
    GeoLocation(
        label="Denver, CO",
        latitude=39.7392,
        longitude=-104.9903,
        provider_id="fixture:den-co",
        country_code="USA",
        region="CO",
        locality="Denver",
        confidence=1.0,
    ),
    GeoLocation(
        label="Salt Lake City, UT",
        latitude=40.7608,
        longitude=-111.8910,
        provider_id="fixture:slc-ut",
        country_code="USA",
        region="UT",
        locality="Salt Lake City",
        confidence=1.0,
    ),
    GeoLocation(
        label="Dallas, TX",
        latitude=32.7767,
        longitude=-96.7970,
        provider_id="fixture:dal-tx",
        country_code="USA",
        region="TX",
        locality="Dallas",
        confidence=1.0,
    ),
    GeoLocation(
        label="Houston, TX",
        latitude=29.7604,
        longitude=-95.3698,
        provider_id="fixture:hou-tx",
        country_code="USA",
        region="TX",
        locality="Houston",
        confidence=1.0,
    ),
    GeoLocation(
        label="Atlanta, GA",
        latitude=33.7490,
        longitude=-84.3880,
        provider_id="fixture:atl-ga",
        country_code="USA",
        region="GA",
        locality="Atlanta",
        confidence=1.0,
    ),
    GeoLocation(
        label="Charlotte, NC",
        latitude=35.2271,
        longitude=-80.8431,
        provider_id="fixture:clt-nc",
        country_code="USA",
        region="NC",
        locality="Charlotte",
        confidence=1.0,
    ),
    GeoLocation(
        label="Los Angeles, CA",
        latitude=34.0522,
        longitude=-118.2437,
        provider_id="fixture:lax-ca",
        country_code="USA",
        region="CA",
        locality="Los Angeles",
        confidence=1.0,
    ),
    GeoLocation(
        label="Phoenix, AZ",
        latitude=33.4484,
        longitude=-112.0740,
        provider_id="fixture:phx-az",
        country_code="USA",
        region="AZ",
        locality="Phoenix",
        confidence=1.0,
    ),
    GeoLocation(
        label="Seattle, WA",
        latitude=47.6062,
        longitude=-122.3321,
        provider_id="fixture:sea-wa",
        country_code="USA",
        region="WA",
        locality="Seattle",
        confidence=1.0,
    ),
    GeoLocation(
        label="Portland, OR",
        latitude=45.5152,
        longitude=-122.6784,
        provider_id="fixture:pdx-or",
        country_code="USA",
        region="OR",
        locality="Portland",
        confidence=1.0,
    ),
    GeoLocation(
        label="Columbus, OH",
        latitude=39.9612,
        longitude=-82.9988,
        provider_id="fixture:cmh-oh",
        country_code="USA",
        region="OH",
        locality="Columbus",
        confidence=1.0,
    ),
    GeoLocation(
        label="Indianapolis, IN",
        latitude=39.7684,
        longitude=-86.1581,
        provider_id="fixture:ind-in",
        country_code="USA",
        region="IN",
        locality="Indianapolis",
        confidence=1.0,
    ),
    GeoLocation(
        label="Kansas City, MO",
        latitude=39.0997,
        longitude=-94.5786,
        provider_id="fixture:mci-mo",
        country_code="USA",
        region="MO",
        locality="Kansas City",
        confidence=1.0,
    ),
    GeoLocation(
        label="Minneapolis, MN",
        latitude=44.9778,
        longitude=-93.2650,
        provider_id="fixture:msp-mn",
        country_code="USA",
        region="MN",
        locality="Minneapolis",
        confidence=1.0,
    ),
    GeoLocation(
        label="Memphis, TN",
        latitude=35.1495,
        longitude=-90.0490,
        provider_id="fixture:mem-tn",
        country_code="USA",
        region="TN",
        locality="Memphis",
        confidence=1.0,
    ),
    GeoLocation(
        label="Nashville, TN",
        latitude=36.1627,
        longitude=-86.7816,
        provider_id="fixture:bna-tn",
        country_code="USA",
        region="TN",
        locality="Nashville",
        confidence=1.0,
    ),
    GeoLocation(
        label="Boston, MA",
        latitude=42.3601,
        longitude=-71.0589,
        provider_id="fixture:bos-ma",
        country_code="USA",
        region="MA",
        locality="Boston",
        confidence=1.0,
    ),
    GeoLocation(
        label="Newark, NJ",
        latitude=40.7357,
        longitude=-74.1724,
        provider_id="fixture:ewr-nj",
        country_code="USA",
        region="NJ",
        locality="Newark",
        confidence=1.0,
    ),
    GeoLocation(
        label="Miami, FL",
        latitude=25.7617,
        longitude=-80.1918,
        provider_id="fixture:mia-fl",
        country_code="USA",
        region="FL",
        locality="Miami",
        confidence=1.0,
    ),
    # Ambiguous cities to exercise user-driven disambiguation UI and tests
    GeoLocation(
        label="Springfield, IL",
        latitude=39.7817,
        longitude=-89.6501,
        provider_id="fixture:spi-il",
        country_code="USA",
        region="IL",
        locality="Springfield",
        confidence=0.95,
    ),
    GeoLocation(
        label="Springfield, MO",
        latitude=37.2090,
        longitude=-93.2923,
        provider_id="fixture:sgf-mo",
        country_code="USA",
        region="MO",
        locality="Springfield",
        confidence=0.94,
    ),
    GeoLocation(
        label="Springfield, MA",
        latitude=42.1015,
        longitude=-72.5898,
        provider_id="fixture:cef-ma",
        country_code="USA",
        region="MA",
        locality="Springfield",
        confidence=0.93,
    ),
)

_STATE_NAMES: dict[str, str] = {
    "NY": "new york",
    "PA": "pennsylvania",
    "IL": "illinois",
    "MI": "michigan",
    "CO": "colorado",
    "UT": "utah",
    "TX": "texas",
    "GA": "georgia",
    "NC": "north carolina",
    "CA": "california",
    "AZ": "arizona",
    "WA": "washington",
    "OR": "oregon",
    "OH": "ohio",
    "IN": "indiana",
    "MO": "missouri",
    "MN": "minnesota",
    "TN": "tennessee",
    "MA": "massachusetts",
    "NJ": "new jersey",
    "FL": "florida",
}


class FixtureGeocodingProvider:
    """Deterministic fixture geocoding provider over curated US freight hubs."""

    provider_name = "fixture_geocoding"
    data_mode = "fixture"

    def search(self, query: str, limit: int = 5) -> list[GeoLocation]:
        cleaned = query.strip()
        if not cleaned:
            return []
        bounded_limit = max(1, min(int(limit), 20))

        # Support direct "lat, lon" input for power-user dispatch workflows.
        coord_match = _COORD_PAIR_RE.match(cleaned)
        if coord_match:
            lat = float(coord_match.group(1))
            lon = float(coord_match.group(2))
            if math.isfinite(lat) and math.isfinite(lon) and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                return [
                    GeoLocation(
                        label=f"{lat:.4f}, {lon:.4f}",
                        latitude=lat,
                        longitude=lon,
                        provider_id=f"fixture:coord:{lat:.4f},{lon:.4f}",
                        confidence=1.0,
                    )
                ]
            return []

        q_lower = cleaned.lower()
        q_tokens = [tok for tok in re.split(r"[\s,]+", q_lower) if tok]

        scored: list[tuple[int, str, GeoLocation]] = []
        for hub in _FIXTURE_HUBS:
            label_lower = hub.label.lower()
            city_lower = (hub.locality or "").lower()
            region_lower = (hub.region or "").lower()
            state_full = _STATE_NAMES.get(hub.region or "", "")
            searchable = f"{label_lower} {state_full}".strip()

            rank: int | None = None
            if label_lower == q_lower:
                rank = 0
            elif city_lower == q_lower:
                rank = 1
            elif label_lower.startswith(q_lower):
                rank = 2
            elif city_lower.startswith(q_lower):
                rank = 3
            elif q_lower in label_lower or (state_full and q_lower in state_full):
                rank = 4
            elif q_tokens and all(
                tok in searchable or tok == region_lower for tok in q_tokens
            ):
                rank = 5

            if rank is not None:
                scored.append((rank, hub.label, hub))

        scored.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in scored[:bounded_limit]]
