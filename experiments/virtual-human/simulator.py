"""Hour-by-hour behavioural simulator for a single persona.

The decision function is rule-based but reads from persona traits, current
internal state, and the environment. Output is a structured event log
suitable for downstream marketing analysis (touchpoint counting,
conversion attribution, segment discovery).

To swap in an LLM-driven policy, replace `decide_action` with a call to
Claude using the same `context` dict as the prompt input.
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from environment import World, make_world
from persona import Persona, sample_persona


# --- Action catalog ---------------------------------------------------------

ACTIONS = {
    "sleep":             {"energy": +0.12, "hunger": +0.05, "mood": +0.02, "cost": 0},
    "morning_routine":   {"energy": -0.02, "hunger": +0.08, "mood": +0.03, "cost": 0},
    "commute":           {"energy": -0.08, "hunger": +0.04, "stress": +0.05, "cost": 320},
    "work":              {"energy": -0.10, "hunger": +0.10, "stress": +0.08, "cost": 0},
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
}


# --- Decision policy --------------------------------------------------------

def _score(persona: Persona, world: World, action: str, rng: random.Random) -> float:
    """Return a relative score for taking `action` right now."""
    s = persona.state
    t = persona.traits
    hour = world.now.hour
    weekend = world.is_weekend
    score = 0.0

    # Time-of-day priors
    if action == "sleep" and (hour < 6 or hour >= 23):
        score += 5
    if action == "morning_routine" and 6 <= hour <= 8:
        score += 4
    if action == "commute" and ((not weekend) and hour in (8, 18)):
        score += 5
    if action == "work" and (not weekend) and 9 <= hour <= 17:
        score += 4
    if action in ("lunch_out", "lunch_konbini") and 11 <= hour <= 13:
        score += 3 + s.hunger * 4
    if action in ("dinner_home", "dinner_out") and 18 <= hour <= 21:
        score += 3 + s.hunger * 4
    if action == "wind_down" and 21 <= hour <= 23:
        score += 3
    if action == "netflix" and (20 <= hour <= 23):
        score += 1.5
    if action == "instagram_scroll" and hour in (7, 12, 21, 22):
        score += 1.2

    # State-driven needs
    if action == "cafe_break" and 14 <= hour <= 16 and s.stress > 0.5:
        score += 2
    if action == "workout" and weekend and 8 <= hour <= 11:
        score += 2 + (1 - s.energy)

    # Personality / preference
    if action == "shopping_apparel":
        score += t.openness * 1.5 + (1 - t.price_sensitivity) * 1.2
        if weekend and 12 <= hour <= 17:
            score += 2
    if action == "online_shopping" and hour in (12, 21, 22):
        score += 1.0 + t.brand_affinity.get("Amazon", 0.5)
    if action == "coworker_chat":
        score += t.extraversion * 1.2

    # Environment effects
    if world.weather == "rainy":
        if action in ("shopping_apparel", "dinner_out"):
            score -= 1.5
        if action in ("netflix", "online_shopping"):
            score += 0.8
    if world.temperature_c >= 25 and action == "cafe_break":
        score += 0.6  # iced drinks
    if world.temperature_c <= 10 and action == "dinner_out":
        score -= 0.5

    # Budget gate
    cost = ACTIONS[action]["cost"]
    if cost > s.wallet_jpy:
        return -999
    if cost > 3000:
        score -= t.price_sensitivity * 1.5

    # Small jitter so ties break stochastically
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


# --- Touchpoint extraction --------------------------------------------------

# Maps actions to marketing touchpoints (channel, candidate brand exposure).
TOUCHPOINTS = {
    "cafe_break":       ("OOH+店舗", ["Starbucks", "Blue Bottle"]),
    "lunch_out":        ("店舗", []),
    "lunch_konbini":    ("店舗", []),
    "shopping_apparel": ("店舗", ["Uniqlo", "ZARA", "MUJI"]),
    "grocery":          ("店舗", []),
    "dinner_out":       ("店舗", []),
    "instagram_scroll": ("Instagram", []),
    "netflix":          ("Netflix", []),
    "online_shopping":  ("EC", ["Amazon"]),
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
                "pre_state": asdict(persona.state) | {},
                "action": action,
                "cost_jpy": ACTIONS[action]["cost"],
                "touchpoint": tp,
            }
        )
        _apply(persona, action)
        events[-1]["post_state"] = asdict(persona.state) | {}
    return events


def summarize(events: list[dict]) -> dict:
    spend = sum(e["cost_jpy"] for e in events)
    by_channel: dict[str, int] = {}
    brand_exposure: dict[str, int] = {}
    for e in events:
        tp = e["touchpoint"]
        if not tp:
            continue
        by_channel[tp["channel"]] = by_channel.get(tp["channel"], 0) + 1
        if tp["brand"]:
            brand_exposure[tp["brand"]] = brand_exposure.get(tp["brand"], 0) + 1
    return {
        "total_spend_jpy": spend,
        "touchpoints_by_channel": by_channel,
        "brand_exposure": brand_exposure,
        "actions": [e["action"] for e in events],
    }


def main() -> None:
    persona = sample_persona()
    start = datetime(2026, 5, 16, 0, 0)  # today, 00:00 JST
    events = simulate_day(persona, start, seed=7)
    summary = summarize(events)

    out_dir = Path(__file__).parent / "out"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "persona.json").write_text(
        json.dumps(persona.snapshot(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "events.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Console digest
    print(f"=== Persona: {persona.traits.name} ({persona.traits.age}) ===")
    print(f"  {persona.traits.occupation} / {persona.traits.city}")
    print()
    print("Hour | Weather  Temp |  Action            | Cost   | Touchpoint")
    print("-" * 78)
    for e in events:
        w = e["world"]
        tp = e["touchpoint"]
        tp_str = f"{tp['channel']}" + (f" ({tp['brand']})" if tp and tp["brand"] else "") if tp else "-"
        print(
            f"{w['hour']:>4} | {w['weather']:<8} {w['temperature_c']:>4}C | "
            f"{e['action']:<18} | {e['cost_jpy']:>5}円 | {tp_str}"
        )
    print()
    print(f"総支出: {summary['total_spend_jpy']:,} 円")
    print(f"チャネル接触: {summary['touchpoints_by_channel']}")
    print(f"ブランド接触: {summary['brand_exposure']}")


if __name__ == "__main__":
    main()
