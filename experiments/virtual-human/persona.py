"""Virtual human persona definition."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from geo import GeoPoint


@dataclass
class Traits:
    name: str
    age: int
    gender: str
    occupation: str
    income_jpy_year: int
    home: GeoPoint
    household: str
    # Big Five (0.0 - 1.0)
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float
    # Marketing-relevant preferences
    brand_affinity: dict[str, float]
    media_diet: dict[str, float]
    price_sensitivity: float       # 0 = luxury seeker, 1 = bargain hunter
    work_from_home: bool = False
    works_weekdays: bool = True


@dataclass
class State:
    mood: float = 0.6
    energy: float = 0.8
    hunger: float = 0.2
    stress: float = 0.3
    wallet_jpy: int = 35000
    location: str = "home"
    last_action: str = "sleep"
    recent_actions: list[str] = field(default_factory=list)  # last 3 ticks


@dataclass
class Persona:
    traits: Traits
    state: State = field(default_factory=State)

    def snapshot(self) -> dict[str, Any]:
        d = asdict(self.traits)
        d["home"] = {
            "name": self.traits.home.name,
            "lat": self.traits.home.lat,
            "lng": self.traits.home.lng,
            "km_from_shimofuri": round(self.traits.home.km_from_shimofuri(), 2),
        }
        return {"traits": d, "state": asdict(self.state)}
