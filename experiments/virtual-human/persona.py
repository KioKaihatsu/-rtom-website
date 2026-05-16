"""Virtual human persona definition."""
from __future__ import annotations

from dataclasses import dataclass, field

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
    workplace_id: str | None = None  # key in places.WORKPLACES, or None

    @property
    def hourly_wage_jpy(self) -> int:
        # Annual / (52 weeks * 5 days * 8 hours), rounded.
        return round(self.income_jpy_year / (52 * 5 * 8))


@dataclass
class State:
    wallet_jpy: int = 35000  # starting cash for the day


@dataclass
class Persona:
    traits: Traits
    state: State = field(default_factory=State)
