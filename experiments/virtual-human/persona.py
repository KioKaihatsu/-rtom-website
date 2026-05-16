"""Virtual human persona definition.

A persona bundles immutable traits (demographics, Big Five) with mutable
state (mood, energy, wallet) that the simulator updates each tick.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Traits:
    name: str
    age: int
    gender: str
    occupation: str
    income_jpy_year: int
    city: str
    household: str
    # Big Five (0.0 - 1.0)
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float
    # Marketing-relevant preferences
    brand_affinity: dict[str, float]
    media_diet: dict[str, float]  # share of attention per channel
    price_sensitivity: float       # 0 = luxury seeker, 1 = bargain hunter


@dataclass
class State:
    mood: float = 0.6        # 0=miserable, 1=elated
    energy: float = 0.8      # 0=exhausted, 1=fresh
    hunger: float = 0.2      # 0=full, 1=starving
    stress: float = 0.3
    wallet_jpy: int = 35000  # available cash this week
    location: str = "home"
    last_action: str = "sleep"


@dataclass
class Persona:
    traits: Traits
    state: State = field(default_factory=State)

    def snapshot(self) -> dict[str, Any]:
        return {"traits": asdict(self.traits), "state": asdict(self.state)}


def sample_persona() -> Persona:
    """Return a single hand-tuned persona for the PoC."""
    traits = Traits(
        name="佐藤 美咲",
        age=29,
        gender="female",
        occupation="広告代理店 アカウントプランナー",
        income_jpy_year=5_200_000,
        city="東京都 世田谷区",
        household="一人暮らし",
        openness=0.78,
        conscientiousness=0.62,
        extraversion=0.55,
        agreeableness=0.70,
        neuroticism=0.48,
        brand_affinity={
            "Starbucks": 0.72,
            "Blue Bottle": 0.81,
            "Uniqlo": 0.65,
            "ZARA": 0.58,
            "MUJI": 0.74,
            "Amazon": 0.88,
        },
        media_diet={
            "Instagram": 0.34,
            "YouTube": 0.22,
            "X": 0.15,
            "TV": 0.08,
            "Podcast": 0.11,
            "News web": 0.10,
        },
        price_sensitivity=0.42,
    )
    return Persona(traits=traits)
