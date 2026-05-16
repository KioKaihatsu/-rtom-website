"""Hour-by-hour behavioural simulator.

Location-aware: persona's distance from 霜降銀座商店街 modulates how often
shotengai-specific actions appear. The Shimofuri Ginza grocery / dining /
stroll actions are the marketing surface we care about.
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from environment import World, make_world
from geo import visit_propensity
from persona import Persona


# --- Action catalog ---------------------------------------------------------

ACTIONS = {
    "sleep":             {"energy": +0.12, "hunger": +0.05, "mood": +0.02, "cost": 0},
    "morning_routine":   {"energy": -0.02, "hunger": +0.08, "mood": +0.03, "cost": 0},
    "commute":           {"energy": -0.08, "hunger": +0.04, "stress": +0.05, "cost": 320},
    "work":              {"energy": -0.10, "hunger": +0.10, "stress": +0.08, "cost": 0},
    "wfh_work":          {"energy": -0.08, "hunger": +0.10, "stress": +0.05, "cost": 0},
    "lunch_out":         {"energy": +0.05, "hunger": -0.55, "mood": +0.06, "cost": 1200},
    "lunch_konbini":     {"energy": +0.03, "hunger": -0.45, "mood": +0.01, "cost": 650},
    "cafe_break":        {"energy": +0.06, "stress": -0.06, "mood": +0.05, "cost": 580},
    "coworker_chat":     {"energy": -0.02, "mood": +0.04, "stress": -0.03, "cost": 0},
    "shopping_apparel":  {"energy": -0.05, "mood": +0.08, "stress": -0.04, "cost": 6800},
    "grocery":           {"energy": -0.04, "mood": +0.01, "cost": 1900},
    "dinner_home":       {"hunger": -0.65, "mood": +0.04, "cost": 0},
    "dinner_out":        {"hunger": -0.65, "mood": +0.10, "stress": -0.05, "cost": 2400},
    "netflix":           {"energy": -0.04, "mood": +0.05, "stress": -0.06, "cost": 0},
    "instagram_scroll":  {"energy": -0.02, "mood": +0.02, "cost": 0},
    "online_shopping":   {"mood": +0.06, "cost": 4200},
    "workout":           {"energy": -0.12, "mood": +0.10, "stress": -0.10, "cost": 0},
    "wind_down":         {"energy": +0.04, "stress": -0.08, "mood": +0.02, "cost": 0},
    # Shimofuri Ginza specific
    "shimofuri_grocery": {"energy": -0.05, "mood": +0.05, "cost": 1600},
    "shimofuri_dining":  {"energy": +0.04, "hunger": -0.65, "mood": +0.12,
                          "stress": -0.07, "cost": 3200},
    "shimofuri_stroll":  {"energy": -0.04, "mood": +0.08, "stress": -0.05, "cost": 800},
}


# --- Decision policy --------------------------------------------------------

def _score(persona: Persona, world: World, action: str, rng: random.Random) -> float:
    s = persona.state
    t = persona.traits
    hour = world.now.hour
    weekend = world.is_weekend
    working_day = (not weekend) and t.works_weekdays
    score = 0.0

    # Time-of-day priors
    if action == "sleep":
        if hour < 6 or hour >= 23:
            score += 5
    if action == "morning_routine" and 6 <= hour <= 8:
        score += 4
    if action == "commute":
        if working_day and not t.work_from_home and hour in (8, 18):
            score += 5
        else:
            score -= 10
    if action == "work":
        if working_day and not t.work_from_home and 9 <= hour <= 17:
            score += 4
        else:
            score -= 10
    if action == "wfh_work":
        if working_day and t.work_from_home and 9 <= hour <= 17:
            score += 4
        else:
            score -= 10
    if action in ("lunch_out", "lunch_konbini") and 11 <= hour <= 13:
        score += 3 + s.hunger * 4
    if action in ("dinner_home", "dinner_out", "shimofuri_dining") and 18 <= hour <= 21:
        score += 3 + s.hunger * 4
    if action == "wind_down" and 21 <= hour <= 23:
        score += 3
    if action == "netflix" and 20 <= hour <= 23:
        score += 1.5
    if action == "instagram_scroll" and hour in (7, 12, 21, 22):
        score += 1.4

    # State-driven needs
    if action == "cafe_break" and 14 <= hour <= 16 and s.stress > 0.5:
        score += 2
    if action == "workout" and weekend and 8 <= hour <= 11:
        score += 2 + (1 - s.energy)
    if action == "grocery" and weekend and 10 <= hour <= 18:
        score += 1.5
    if action == "shimofuri_grocery" and 10 <= hour <= 19:
        score += 1.4
    if action == "shimofuri_stroll" and weekend and 11 <= hour <= 17:
        score += 1.6

    # Personality / preference
    if action == "shopping_apparel":
        score += t.openness * 1.0 + (1 - t.price_sensitivity) * 1.0
        if weekend and 12 <= hour <= 17:
            score += 1.5
    if action == "online_shopping" and hour in (12, 21, 22):
        score += 0.8 + t.brand_affinity.get("Amazon", 0.5)
    if action == "coworker_chat":
        if working_day and not t.work_from_home and 12 <= hour <= 17:
            score += t.extraversion * 1.2
        else:
            score -= 5

    # Shimofuri Ginza distance gate
    if action.startswith("shimofuri_"):
        propensity = visit_propensity(t.home.km_from_shimofuri())
        affinity = t.brand_affinity.get("Riverbed in Otherworld", 0.3)
        score *= propensity * (0.5 + affinity)
        if action == "shimofuri_dining":
            score += affinity * 1.5

    # Environment effects
    if world.weather == "rainy":
        if action in ("shopping_apparel", "dinner_out", "shimofuri_stroll"):
            score -= 1.5
        if action in ("netflix", "online_shopping"):
            score += 0.8
    if world.temperature_c >= 25 and action == "cafe_break":
        score += 0.6
    if world.temperature_c <= 10 and action in ("dinner_out", "shimofuri_dining"):
        score -= 0.3

    # Repetition penalty — discourage same action 3+ ticks in a row
    streak = sum(1 for a in s.recent_actions if a == action)
    if streak >= 2 and action not in ("sleep", "work", "wfh_work"):
        score -= streak * 2.0

    # Budget gate
    cost = ACTIONS[action]["cost"]
    if cost > s.wallet_jpy:
        return -999
    if cost > 3000:
        score -= t.price_sensitivity * 1.5

    score += rng.uniform(-0.15, 0.15)
    return score


def decide_action(persona: Persona, world: World, rng: random.Random) -> str:
    scored = [(a, _score(persona, world, a, rng)) for a in ACTIONS]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


def _apply(persona: Persona, action: str) -> None:
    effects = ACTIONS[action]
    s = persona.state
    for k, v in effects.items():
        if k == "cost":
            s.wallet_jpy -= v
        else:
            current = getattr(s, k)
            setattr(s, k, max(0.0, min(1.0, current + v)))
    s.last_action = action
    s.recent_actions = (s.recent_actions + [action])[-3:]


# --- Touchpoint extraction --------------------------------------------------

TOUCHPOINTS = {
    "cafe_break":        ("OOH+店舗", ["Starbucks", "Blue Bottle"]),
    "lunch_out":         ("店舗", []),
    "lunch_konbini":     ("店舗", []),
    "shopping_apparel":  ("店舗", ["Uniqlo", "ZARA", "MUJI"]),
    "grocery":           ("店舗", []),
    "dinner_out":        ("店舗", []),
    "instagram_scroll":  ("Instagram", []),
    "netflix":           ("Netflix", []),
    "online_shopping":   ("EC", ["Amazon"]),
    "shimofuri_grocery": ("霜降銀座", []),
    "shimofuri_dining":  ("霜降銀座", ["Riverbed in Otherworld"]),
    "shimofuri_stroll":  ("霜降銀座", []),
}


def touchpoint(persona: Persona, action: str, rng: random.Random) -> dict | None:
    if action not in TOUCHPOINTS:
        return None
    channel, candidates = TOUCHPOINTS[action]
    brand = None
    if candidates:
        weights = [persona.traits.brand_affinity.get(b, 0.3) for b in candidates]
        brand = rng.choices(candidates, weights=weights, k=1)[0]
    return {"channel": channel, "brand": brand}


# --- Run loop ---------------------------------------------------------------

def simulate_day(
    persona: Persona, start: datetime, seed: int = 42
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    events: list[dict[str, Any]] = []
    for hour in range(24):
        world = make_world(start, hour, rng)
        action = decide_action(persona, world, rng)
        tp = touchpoint(persona, action, rng)
        events.append(
            {
                "tick": hour,
                "world": world.snapshot(),
                "action": action,
                "cost_jpy": ACTIONS[action]["cost"],
                "touchpoint": tp,
                "state": asdict(persona.state),
            }
        )
        _apply(persona, action)
    return events
