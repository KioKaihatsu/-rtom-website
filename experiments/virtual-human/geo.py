"""Geographic helpers.

Origin is 霜降銀座商店街 (Shimofuri Ginza Shotengai), Komagome, Tokyo.
We use a flat-earth approximation (good enough for <30km in Tokyo).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


SHIMOFURI_LAT = 35.7414
SHIMOFURI_LNG = 139.7448


@dataclass(frozen=True)
class GeoPoint:
    name: str
    lat: float
    lng: float

    def km_from_shimofuri(self) -> float:
        # 1 degree latitude ~= 111 km, longitude scaled by cos(lat).
        dlat = (self.lat - SHIMOFURI_LAT) * 111.0
        dlng = (self.lng - SHIMOFURI_LNG) * 111.0 * math.cos(math.radians(SHIMOFURI_LAT))
        return math.hypot(dlat, dlng)


def visit_propensity(km: float) -> float:
    """Probability multiplier for visiting Shimofuri Ginza.

    Walking distance (<1.2km): near-daily candidate.
    1.2-5km: weekend / occasional.
    5-10km: only with intent.
    >10km: rare destination.
    """
    if km < 1.2:
        return 1.0
    if km < 5:
        return 0.55 * math.exp(-(km - 1.2) / 3.0)
    if km < 10:
        return 0.15 * math.exp(-(km - 5) / 4.0)
    return 0.03 * math.exp(-(km - 10) / 5.0)
