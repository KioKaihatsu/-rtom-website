"""Environment model: clock, weather, temperature, day-of-week effects."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class World:
    now: datetime
    temperature_c: float
    weather: str          # sunny / cloudy / rainy
    humidity: float       # 0..1
    is_weekend: bool

    def snapshot(self) -> dict:
        return {
            "datetime": self.now.isoformat(),
            "hour": self.now.hour,
            "weekday": self.now.strftime("%A"),
            "is_weekend": self.is_weekend,
            "temperature_c": round(self.temperature_c, 1),
            "weather": self.weather,
            "humidity": round(self.humidity, 2),
        }


def _diurnal_temp(hour: int, base: float, amplitude: float) -> float:
    # Coldest around 5am, warmest around 2pm.
    phase = (hour - 14) / 24 * 2 * math.pi
    return base + amplitude * math.cos(phase)


def make_world(start: datetime, hour_offset: int, rng: random.Random) -> World:
    now = start + timedelta(hours=hour_offset)
    base_temp = 18.0  # mid-May Tokyo average
    temp = _diurnal_temp(now.hour, base=base_temp, amplitude=4.5)
    temp += rng.uniform(-1.2, 1.2)
    weather = rng.choices(
        ["sunny", "cloudy", "rainy"], weights=[0.55, 0.30, 0.15], k=1
    )[0]
    humidity = 0.55 + (0.20 if weather == "rainy" else 0.0) + rng.uniform(-0.05, 0.05)
    return World(
        now=now,
        temperature_c=temp,
        weather=weather,
        humidity=max(0.0, min(1.0, humidity)),
        is_weekend=now.weekday() >= 5,
    )
