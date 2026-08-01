import math

from engagement_course.models import Address


def haversine(strAddrA: str, strAddrB: str) -> float:
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """

    addressA = Address(strAddrA)
    addressB = Address(strAddrB)
    print(f"Address A: {addressA}, Address B: {addressB}")
    lat1, lon1 = addressA.coordinates
    lat2, lon2 = addressB.coordinates

    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers. Use 3956 for miles
    return c * r