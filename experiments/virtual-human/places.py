"""Catalog of real-world places used by the simulation.

Coordinates are approximate but plotted on real Tokyo geography so the
HTML monitor can render movement on OpenStreetMap tiles.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal[
    "home", "workplace", "shotengai", "rio", "supermarket", "konbini",
    "cafe", "restaurant", "apparel", "park", "station", "school", "hospital",
]


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    lat: float
    lng: float
    kind: Kind


# 霜降銀座 specific
SHIMOFURI_GINZA = Place(
    "shimofuri_ginza", "霜降銀座商店街", 35.7414, 139.7448, "shotengai"
)
RIO = Place(
    "rio", "Riverbed in Otherworld", 35.7418, 139.7445, "rio"
)

# Workplaces
WORKPLACES: dict[str, Place] = {
    "bank_otemachi": Place(
        "bank_otemachi", "メガバンク本店 (大手町)", 35.6852, 139.7660, "workplace"
    ),
    "komagome_hospital": Place(
        "komagome_hospital", "都立駒込病院", 35.7367, 139.7472, "hospital"
    ),
    "ikebukuro_salon": Place(
        "ikebukuro_salon", "美容室 (池袋)", 35.7320, 139.7155, "workplace"
    ),
    "oyama_izakaya": Place(
        "oyama_izakaya", "中村屋 (大山駅前)", 35.7505, 139.6997, "restaurant"
    ),
    "waseda_univ": Place(
        "waseda_univ", "早稲田大学", 35.7062, 139.7195, "school"
    ),
    "shibuya_agency": Place(
        "shibuya_agency", "広告代理店 (渋谷)", 35.6594, 139.7005, "workplace"
    ),
    "kita_kuyakusho": Place(
        "kita_kuyakusho", "北区役所", 35.7528, 139.7340, "workplace"
    ),
    "kawaguchi_factory": Place(
        "kawaguchi_factory", "自動車部品工場 (川口)", 35.8120, 139.7155, "workplace"
    ),
}

# Stations (used as commute waypoint hint)
KOMAGOME_STATION = Place(
    "komagome_st", "JR駒込駅", 35.7367, 139.7475, "station"
)


def all_places() -> list[Place]:
    return [SHIMOFURI_GINZA, RIO, KOMAGOME_STATION, *WORKPLACES.values()]
