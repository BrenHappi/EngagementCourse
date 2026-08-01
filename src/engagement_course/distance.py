import math
from typing import Optional

import requests

GEOCODER_URL = "https://data.geopf.fr/geocodage/search"


def geocode_address(address: str) -> Optional[tuple[float, float]]:
    if not address:
        return None

    params = {
        "q": address,
        "autocomplete": 1,
        "returntruegeometry": "false",
        "limit": 1,
    }
    try:
        response = requests.get(GEOCODER_URL, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None

    data = response.json()
    features = data.get("features") or []
    if not features:
        return None

    coordinates = features[0]["geometry"]["coordinates"]
    return float(coordinates[1]), float(coordinates[0])


def haversine_from_coordinates(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c


def haversine(strAddrA: str, strAddrB: str) -> float:
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    coordinates_a = geocode_address(strAddrA)
    coordinates_b = geocode_address(strAddrB)
    if coordinates_a is None or coordinates_b is None:
        raise ValueError("Could not geocode one or both addresses")

    lat1, lon1 = coordinates_a
    lat2, lon2 = coordinates_b
    return haversine_from_coordinates(lat1, lon1, lat2, lon2)