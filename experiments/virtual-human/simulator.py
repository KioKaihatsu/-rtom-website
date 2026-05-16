"""Hour-by-hour behavioural simulator.

Each tick produces a structured event with the persona's geographic location,
financial deltas, and marketing touchpoints. Output is suitable for the map
monitor in monitor.py.
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict
from datetime import datetime
from typing import Any

from environment import World, make_world
from geo import visit_propensity
from persona import Persona
from places import (
    SHIMOFURI_GINZA,
    RIO,
    WORKPLACES,
    Place,
)


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

WORK_ACTIONS = {"work", "wfh_work"}


# --- Decision policy --------------------------------------------------------

def _score(persona: Persona, world: World, action: str, rng: random.Random) -> float:
    s = persona.state
    t = persona.traits
    hour = world.now.hour
    weekend = world.is_weekend
    working_day = (not weekend) and t.works_weekdays
    score = 0.0

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

    if action == "cafe_break" and 14 <= hour <= 16 and s.stress > 0.5:
        score += 2
    if action == "workout" and weekend and 8 <= hour <= 11:
        # Personality-weighted: conscientious / young people work out more.
        score += t.conscientiousness * 1.5 + max(0, (35 - t.age) / 30)
    if action == "grocery" and weekend and 10 <= hour <= 18:
        score += 1.0
    if action == "shimofuri_grocery" and 10 <= hour <= 19:
        score += 1.2
    if action == "shimofuri_stroll" and weekend and 11 <= hour <= 17:
        score += 1.4

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

    if action.startswith("shimofuri_"):
        propensity = visit_propensity(t.home.km_from_shimofuri())
        affinity = t.brand_affinity.get("Riverbed in Otherworld", 0.3)
        score *= propensity * (0.5 + affinity)
        if action == "shimofuri_dining":
            score += affinity * 1.5

    if world.weather == "rainy":
        if action in ("shopping_apparel", "dinner_out", "shimofuri_stroll"):
            score -= 1.5
        if action in ("netflix", "online_shopping"):
            score += 0.8
    if world.temperature_c >= 25 and action == "cafe_break":
        score += 0.6
    if world.temperature_c <= 10 and action in ("dinner_out", "shimofuri_dining"):
        score -= 0.3

    streak = sum(1 for a in s.recent_actions if a == action)
    if streak >= 2 and action not in ("sleep", "work", "wfh_work"):
        score -= streak * 2.0

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


# --- Location resolution ---------------------------------------------------

def _home_place(persona: Persona) -> Place:
    h = persona.traits.home
    return Place(f"home_{persona.traits.name}", h.name, h.lat, h.lng, "home")


def _near(base_lat: float, base_lng: float, jitter: float, rng: random.Random):
    """Tiny offset so multiple personas at same place don't overlap exactly."""
    return (
        base_lat + rng.uniform(-jitter, jitter),
        base_lng + rng.uniform(-jitter, jitter),
    )


def resolve_location(
    persona: Persona, action: str, rng: random.Random
) -> tuple[Place, float, float]:
    """Return (canonical place, jittered lat, jittered lng)."""
    t = persona.traits
    home = _home_place(persona)
    work = WORKPLACES.get(t.workplace_id) if t.workplace_id else None

    # Shimofuri Ginza specific
    if action == "shimofuri_dining":
        lat, lng = _near(RIO.lat, RIO.lng, 0.00015, rng)
        return RIO, lat, lng
    if action.startswith("shimofuri_"):
        lat, lng = _near(SHIMOFURI_GINZA.lat, SHIMOFURI_GINZA.lng, 0.00040, rng)
        return SHIMOFURI_GINZA, lat, lng

    # Work area
    if action in WORK_ACTIONS or action == "coworker_chat":
        if work and action != "wfh_work":
            lat, lng = _near(work.lat, work.lng, 0.00060, rng)
            return work, lat, lng
        # WFH or no workplace → at home
        lat, lng = _near(home.lat, home.lng, 0.00040, rng)
        return home, lat, lng

    if action == "commute":
        # End of commute hour = AT work (morning) or AT home (evening).
        # Caller decides based on hour, but we return workplace by default;
        # the simulator overrides for evening commute below.
        if work:
            lat, lng = _near(work.lat, work.lng, 0.00060, rng)
            return work, lat, lng
        return home, home.lat, home.lng

    if action in ("lunch_out", "lunch_konbini", "cafe_break"):
        anchor = work if work else home
        lat, lng = _near(anchor.lat, anchor.lng, 0.0012, rng)  # ~120m radius
        return anchor, lat, lng

    if action == "shopping_apparel":
        # Shopping districts: choose the closest of Ikebukuro/Shinjuku/Shibuya.
        candidates = [
            ("ikebukuro", 35.7295, 139.7110),
            ("shinjuku", 35.6896, 139.7006),
            ("shibuya", 35.6594, 139.7005),
        ]
        d_min = min(candidates, key=lambda c: (c[1] - home.lat) ** 2 + (c[2] - home.lng) ** 2)
        lat, lng = _near(d_min[1], d_min[2], 0.0020, rng)
        return Place(d_min[0], d_min[0].title(), d_min[1], d_min[2], "apparel"), lat, lng

    if action == "dinner_out":
        lat, lng = _near(home.lat, home.lng, 0.0020, rng)
        return Place("dinner_out", "近所の飲食店", home.lat, home.lng, "restaurant"), lat, lng

    if action == "grocery":
        lat, lng = _near(home.lat, home.lng, 0.0018, rng)
        return Place("grocery_local", "近所のスーパー", home.lat, home.lng, "supermarket"), lat, lng

    if action == "workout":
        lat, lng = _near(home.lat, home.lng, 0.0025, rng)
        return Place("park_local", "近所の公園", home.lat, home.lng, "park"), lat, lng

    # Default: at home
    lat, lng = _near(home.lat, home.lng, 0.0001, rng)
    return home, lat, lng


# --- State updates ---------------------------------------------------------

def _apply(persona: Persona, action: str) -> None:
    effects = ACTIONS[action]
    s = persona.state
    for k, v in effects.items():
        if k == "cost":
            s.wallet_jpy -= v
            s.spent_today_jpy += v
        else:
            current = getattr(s, k)
            setattr(s, k, max(0.0, min(1.0, current + v)))
    s.last_action = action
    s.recent_actions = (s.recent_actions + [action])[-3:]

    if action in WORK_ACTIONS:
        wage = persona.traits.hourly_wage_jpy
        s.wallet_jpy += wage
        s.earned_today_jpy += wage


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    # Flat-earth approximation good enough for <30km city-scale tracks.
    dlat = (lat2 - lat1) * 111.0
    dlng = (lng2 - lng1) * 111.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dlat, dlng)


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
    prev_lat = persona.traits.home.lat
    prev_lng = persona.traits.home.lng

    for hour in range(24):
        world = make_world(start, hour, rng)
        action = decide_action(persona, world, rng)

        # For 18:00 commute (evening), the destination is HOME, not workplace.
        place, lat, lng = resolve_location(persona, action, rng)
        if action == "commute" and hour >= 17:
            home = _home_place(persona)
            place = home
            lat, lng = _near(home.lat, home.lng, 0.00050, rng)

        # Distance traveled since last tick
        dist = _haversine_km(prev_lat, prev_lng, lat, lng)
        persona.state.distance_km_today += dist
        prev_lat, prev_lng = lat, lng

        _apply(persona, action)
        tp = touchpoint(persona, action, rng)

        events.append({
            "tick": hour,
            "world": world.snapshot(),
            "action": action,
            "place_id": place.id,
            "place_name": place.name,
            "place_kind": place.kind,
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "tick_distance_km": round(dist, 3),
            "cost_jpy": ACTIONS[action]["cost"],
            "wage_jpy": persona.traits.hourly_wage_jpy if action in WORK_ACTIONS else 0,
            "touchpoint": tp,
            "state": asdict(persona.state),
        })
    return events
