"""Static country -> hub coordinates, used to seed shipment map markers.

Not a real geocoder — Atlas Freight only ships between a handful of known
lanes, so a lookup table is enough to plot origin/destination pins without
pulling in an external geocoding API/key.
"""
from typing import Optional, Tuple

COUNTRY_HUB_COORDS: dict[str, Tuple[float, float]] = {
    "usa": (40.6413, -73.7781),        # JFK, New York
    "united states": (40.6413, -73.7781),
    "ghana": (5.6052, -0.1719),        # Kotoka Intl, Accra
    "uk": (51.4700, -0.4543),          # Heathrow, London
    "united kingdom": (51.4700, -0.4543),
    "nigeria": (6.5774, 3.3211),       # Murtala Muhammed, Lagos
    "china": (31.1443, 121.8083),      # Pudong, Shanghai
    "uae": (25.2532, 55.3657),         # Dubai Intl
    "canada": (43.6777, -79.6248),     # Toronto Pearson
}


def resolve_country_coords(country: Optional[str]) -> Optional[Tuple[float, float]]:
    if not country:
        return None
    return COUNTRY_HUB_COORDS.get(country.strip().lower())
