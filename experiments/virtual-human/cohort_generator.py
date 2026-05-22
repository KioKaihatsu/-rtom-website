"""関東圏のコホート自動生成器。

人口統計（年齢・性別・職業・所得・地域・性格）から N 人をサンプルし、
ec_events と互換のシンプルなペルソナ構造を返す。
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Any

# ============================================================================
# Demographic distributions (Kanto, adult population, EC-active)
# ============================================================================

# Age distribution (18-79), weighted toward working age
AGE_BUCKETS = [
    (18, 24, 0.08),
    (25, 29, 0.07),
    (30, 34, 0.08),
    (35, 39, 0.09),
    (40, 44, 0.10),
    (45, 49, 0.10),
    (50, 54, 0.09),
    (55, 59, 0.08),
    (60, 64, 0.08),
    (65, 69, 0.08),
    (70, 79, 0.15),
]

# Occupation: (label, weight, base_income, template_id)
OCCUPATIONS = [
    ("会社員",          0.28, 4_800_000, "office"),
    ("公務員",          0.05, 5_500_000, "office"),
    ("看護師",          0.02, 4_800_000, "healthcare"),
    ("教員",            0.03, 5_400_000, "office"),
    ("販売員",          0.06, 3_200_000, "retail"),
    ("飲食店",          0.04, 3_500_000, "shift"),
    ("工場勤務",         0.04, 3_900_000, "shift"),
    ("ITエンジニア",      0.05, 6_800_000, "wfh"),
    ("デザイナー",        0.02, 4_500_000, "wfh"),
    ("フリーランス",       0.03, 4_400_000, "wfh"),
    ("経営者・役員",       0.02, 11_500_000, "office"),
    ("主婦・主夫",        0.10, 1_500_000, "home"),
    ("大学生",          0.06, 1_000_000, "student"),
    ("退職",            0.18, 2_700_000, "retired"),
    ("パート",          0.02, 1_800_000, "shift"),
]

# Prefecture: (name, weight, lat_min, lat_max, lng_min, lng_max)
PREFECTURES = [
    ("東京都23区",    0.27, 35.55, 35.82, 139.55, 139.92),
    ("東京都市部",    0.10, 35.55, 35.83, 139.18, 139.55),
    ("神奈川県",      0.18, 35.20, 35.65, 139.10, 139.78),
    ("埼玉県",       0.14, 35.78, 36.20, 139.10, 139.85),
    ("千葉県",       0.13, 35.35, 35.95, 139.85, 140.55),
    ("茨城県",       0.08, 35.85, 36.95, 139.85, 140.85),
    ("栃木県",       0.05, 36.30, 37.15, 139.30, 140.30),
    ("群馬県",       0.05, 36.10, 37.10, 138.40, 139.80),
]

# ============================================================================
# Simplified persona — flat data class, no GeoPoint dependency
# ============================================================================

@dataclass
class SimpleTraits:
    name: str
    age: int
    gender: str
    occupation: str
    template: str               # schedule template id
    income_jpy_year: int
    prefecture: str
    home_lat: float
    home_lng: float
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float
    brand_affinity: dict[str, float]
    work_from_home: bool
    works_weekdays: bool

    @property
    def hourly_wage_jpy(self) -> int:
        return round(self.income_jpy_year / (52 * 5 * 8))


@dataclass
class SimplePersona:
    traits: SimpleTraits
    # No mutable state needed for cohort analytics
    state: Any = field(default=None)


# ============================================================================
# Sampling helpers
# ============================================================================

def _weighted_choice(items, rng: random.Random):
    weights = [it[-1] if isinstance(it, tuple) else 1 for it in items]
    return rng.choices(items, weights=weights, k=1)[0]


def _sample_age(rng: random.Random) -> int:
    w = [b[2] for b in AGE_BUCKETS]
    bucket = rng.choices(AGE_BUCKETS, weights=w, k=1)[0]
    return rng.randint(bucket[0], bucket[1])


def _sample_occupation(age: int, gender: str, rng: random.Random):
    """Pick occupation aligned with age & gender."""
    # Constrain by age:
    if age >= 65:
        # mostly retired or part-time
        pool = [o for o in OCCUPATIONS if o[3] in ("retired", "shift", "home")]
        weights = [3 if o[3] == "retired" else 1 for o in pool]
        return rng.choices(pool, weights=weights, k=1)[0]
    if age <= 22:
        pool = [("大学生", 0.7, 1_000_000, "student"),
                ("パート",  0.2, 1_500_000, "shift"),
                ("販売員",  0.1, 2_800_000, "retail")]
        weights = [p[1] for p in pool]
        return rng.choices(pool, weights=weights, k=1)[0]
    # Working age (23-64)
    pool = [o for o in OCCUPATIONS
            if o[3] not in ("retired", "student")]
    # Bias housewives toward female
    weights = []
    for o in pool:
        w = o[1]
        if o[0] == "主婦・主夫":
            w *= 1.8 if gender == "female" else 0.2
        if o[0] == "経営者・役員" and age < 35:
            w *= 0.3
        weights.append(w)
    return rng.choices(pool, weights=weights, k=1)[0]


def _sample_income(occ_base: int, age: int, rng: random.Random) -> int:
    """Log-normal-ish income around occupation base, modulated by age."""
    # Age multiplier: salary curve peaks around 50
    if age < 25:
        age_mult = 0.55
    elif age < 30:
        age_mult = 0.75
    elif age < 40:
        age_mult = 1.0
    elif age < 50:
        age_mult = 1.15
    elif age < 60:
        age_mult = 1.10
    else:
        age_mult = 0.8
    base = occ_base * age_mult
    # Log-normal noise (sigma ~ 0.3)
    income = base * math.exp(rng.gauss(0, 0.3))
    return max(800_000, int(income // 10_000) * 10_000)


def _sample_prefecture(rng: random.Random):
    w = [p[1] for p in PREFECTURES]
    return rng.choices(PREFECTURES, weights=w, k=1)[0]


def _sample_big5(age: int, rng: random.Random) -> tuple[float, ...]:
    # Truncated normal around 0.5, sigma 0.15
    def s():
        return max(0.05, min(0.95, rng.gauss(0.5, 0.15)))
    o, c, e, a, n = s(), s(), s(), s(), s()
    # Conscientiousness rises mildly with age
    c = min(0.95, c + (age - 30) * 0.003)
    return o, c, e, a, n


def _derive_brand_affinity(
    age: int, gender: str, income: int, openness: float, rng: random.Random
) -> dict[str, float]:
    """Per-persona brand affinity scores."""
    def base(brand: str) -> float:
        x = 0.4
        if brand == "Amazon":
            x = 0.55 + (0.20 if age < 50 else 0.10) + openness * 0.10
        elif brand == "Uniqlo":
            x = 0.65
        elif brand == "MUJI":
            x = 0.50 + openness * 0.20
        elif brand == "Starbucks":
            x = 0.55 if age < 45 else 0.35
        elif brand == "Blue Bottle":
            x = 0.50 + openness * 0.25 - (0.20 if age > 50 else 0)
        elif brand == "ZARA":
            x = 0.55 - (age - 25) * 0.015
        elif brand == "Riverbed in Otherworld":
            x = 0.40 + openness * 0.20
        x += rng.gauss(0, 0.10)
        return max(0.05, min(0.95, x))
    return {b: round(base(b), 2) for b in [
        "Amazon", "Uniqlo", "MUJI", "Starbucks", "Blue Bottle",
        "ZARA", "Riverbed in Otherworld",
    ]}


def _sample_name(gender: str, rng: random.Random) -> str:
    sei = rng.choice([
        "佐藤", "鈴木", "高橋", "田中", "渡辺", "伊藤", "山本", "中村",
        "小林", "加藤", "吉田", "山田", "佐々木", "山口", "松本", "井上",
        "木村", "林", "斎藤", "清水", "山崎", "森", "池田", "橋本",
        "石川", "前田", "藤田", "後藤", "岡田", "長谷川",
    ])
    if gender == "male":
        mei = rng.choice([
            "翔", "蓮", "陽翔", "颯太", "湊", "樹", "悠人", "大翔",
            "健太", "誠", "拓海", "翼", "和也", "亮", "雄太", "達也",
            "浩二", "智也", "貴志", "克彦", "雅人", "正樹", "義男", "孝雄",
        ])
    else:
        mei = rng.choice([
            "陽菜", "結愛", "凛", "葵", "美咲", "結衣", "桜", "芽依",
            "彩", "麻衣", "由美", "智子", "美穂", "彩花", "千尋", "理恵",
            "京子", "節子", "悦子", "ハル", "綾", "莉子", "心春", "杏",
        ])
    return f"{sei} {mei}"


# ============================================================================
# Cohort generation
# ============================================================================

def generate_cohort(n: int = 1000, seed: int = 42) -> list[SimplePersona]:
    rng = random.Random(seed)
    cohort: list[SimplePersona] = []
    used_names: set[str] = set()
    for i in range(n):
        age = _sample_age(rng)
        gender = "male" if rng.random() < 0.49 else "female"
        occ = _sample_occupation(age, gender, rng)
        income = _sample_income(occ[2], age, rng)
        prefecture = _sample_prefecture(rng)
        # jittered home coord
        lat = rng.uniform(prefecture[2], prefecture[3])
        lng = rng.uniform(prefecture[4], prefecture[5])
        o, c, e, a, neu = _sample_big5(age, rng)
        # Unique-ish names: append index suffix for collisions
        name = _sample_name(gender, rng)
        if name in used_names:
            name = f"{name}_{i}"
        used_names.add(name)
        affinity = _derive_brand_affinity(age, gender, income, o, rng)
        traits = SimpleTraits(
            name=name,
            age=age,
            gender=gender,
            occupation=occ[0],
            template=occ[3],
            income_jpy_year=income,
            prefecture=prefecture[0],
            home_lat=round(lat, 5),
            home_lng=round(lng, 5),
            openness=round(o, 2),
            conscientiousness=round(c, 2),
            extraversion=round(e, 2),
            agreeableness=round(a, 2),
            neuroticism=round(neu, 2),
            brand_affinity=affinity,
            work_from_home=(occ[3] == "wfh"),
            works_weekdays=(occ[3] not in ("retired", "home", "student")),
        )
        cohort.append(SimplePersona(traits=traits))
    return cohort


# ============================================================================
# Lightweight schedule templates for purchase timing
# ============================================================================

def schedule_template(template_id: str, weekend: bool) -> list[dict]:
    """Returns a minimal segment list usable by ec_events._timing_pool.

    Each segment is just {"s": start_min, "e": end_min, "act": activity,
    "mode": "stay"|"train"}.  Used only to drive purchase timing logic.
    """
    def hm(h, m=0): return h * 60 + m

    if template_id == "office":
        if weekend:
            return [
                {"s": 0,        "e": hm(8),  "act": "sleep",            "mode": "stay"},
                {"s": hm(8),    "e": hm(10), "act": "morning_routine",  "mode": "stay"},
                {"s": hm(10),   "e": hm(13), "act": "leisure",          "mode": "stay"},
                {"s": hm(13),   "e": hm(14), "act": "lunch_home",       "mode": "stay"},
                {"s": hm(14),   "e": hm(18), "act": "leisure",          "mode": "stay"},
                {"s": hm(18),   "e": hm(20), "act": "dinner_home",      "mode": "stay"},
                {"s": hm(20),   "e": hm(23), "act": "tv_time",          "mode": "stay"},
                {"s": hm(23),   "e": 1440,   "act": "sleep",            "mode": "stay"},
            ]
        return [
            {"s": 0,        "e": hm(6, 30), "act": "sleep",            "mode": "stay"},
            {"s": hm(6, 30),"e": hm(7, 30), "act": "morning_routine",  "mode": "stay"},
            {"s": hm(7, 30),"e": hm(8, 15), "act": "train",            "mode": "train"},
            {"s": hm(8, 15),"e": hm(12),    "act": "work",             "mode": "stay"},
            {"s": hm(12),   "e": hm(13),    "act": "lunch_home",       "mode": "stay"},
            {"s": hm(13),   "e": hm(18),    "act": "work",             "mode": "stay"},
            {"s": hm(18),   "e": hm(18,45), "act": "train",            "mode": "train"},
            {"s": hm(18,45),"e": hm(20),    "act": "dinner_home",      "mode": "stay"},
            {"s": hm(20),   "e": hm(22,30), "act": "leisure",          "mode": "stay"},
            {"s": hm(22,30),"e": hm(23,30), "act": "wind_down",        "mode": "stay"},
            {"s": hm(23,30),"e": 1440,      "act": "sleep",            "mode": "stay"},
        ]

    if template_id == "wfh":
        return [
            {"s": 0,        "e": hm(7,30),  "act": "sleep",            "mode": "stay"},
            {"s": hm(7,30), "e": hm(9),     "act": "morning_routine",  "mode": "stay"},
            {"s": hm(9),    "e": hm(12),    "act": "wfh_work",         "mode": "stay"},
            {"s": hm(12),   "e": hm(13),    "act": "lunch_home",       "mode": "stay"},
            {"s": hm(13),   "e": hm(18),    "act": "wfh_work",         "mode": "stay"},
            {"s": hm(18),   "e": hm(19,30), "act": "dinner_home",      "mode": "stay"},
            {"s": hm(19,30),"e": hm(23),    "act": "leisure",          "mode": "stay"},
            {"s": hm(23),   "e": 1440,      "act": "sleep",            "mode": "stay"},
        ]

    if template_id == "student":
        if weekend:
            return [
                {"s": 0,       "e": hm(11),    "act": "sleep",          "mode": "stay"},
                {"s": hm(11),  "e": hm(13),    "act": "leisure",        "mode": "stay"},
                {"s": hm(13),  "e": hm(18),    "act": "leisure",        "mode": "stay"},
                {"s": hm(18),  "e": hm(20),    "act": "dinner_home",    "mode": "stay"},
                {"s": hm(20),  "e": hm(24),    "act": "instagram_scroll","mode": "stay"},
                {"s": hm(24),  "e": 1440,      "act": "sleep",          "mode": "stay"},
            ]
        return [
            {"s": 0,       "e": hm(8),     "act": "sleep",          "mode": "stay"},
            {"s": hm(8),   "e": hm(9),     "act": "morning_routine","mode": "stay"},
            {"s": hm(9),   "e": hm(16,30), "act": "study_home",     "mode": "stay"},
            {"s": hm(16,30),"e": hm(19),   "act": "leisure",        "mode": "stay"},
            {"s": hm(19),  "e": hm(20),    "act": "dinner_home",    "mode": "stay"},
            {"s": hm(20),  "e": hm(24),    "act": "instagram_scroll","mode": "stay"},
            {"s": hm(24),  "e": 1440,      "act": "sleep",          "mode": "stay"},
        ]

    if template_id == "retired":
        return [
            {"s": 0,       "e": hm(6,30),  "act": "sleep",          "mode": "stay"},
            {"s": hm(6,30),"e": hm(8),     "act": "morning_routine","mode": "stay"},
            {"s": hm(8),   "e": hm(12),    "act": "leisure",        "mode": "stay"},
            {"s": hm(12),  "e": hm(13),    "act": "lunch_home",     "mode": "stay"},
            {"s": hm(13),  "e": hm(18),    "act": "leisure",        "mode": "stay"},
            {"s": hm(18),  "e": hm(20),    "act": "dinner_home",    "mode": "stay"},
            {"s": hm(20),  "e": hm(22),    "act": "tv_time",        "mode": "stay"},
            {"s": hm(22),  "e": 1440,      "act": "sleep",          "mode": "stay"},
        ]

    if template_id == "home":   # housewife/husband
        return [
            {"s": 0,       "e": hm(6),     "act": "sleep",          "mode": "stay"},
            {"s": hm(6),   "e": hm(8,30),  "act": "morning_routine_w_kids","mode": "stay"},
            {"s": hm(8,30),"e": hm(11),    "act": "housework",      "mode": "stay"},
            {"s": hm(11),  "e": hm(13),    "act": "errands",        "mode": "stay"},
            {"s": hm(13),  "e": hm(15),    "act": "lunch_home",     "mode": "stay"},
            {"s": hm(15),  "e": hm(18),    "act": "childcare",      "mode": "stay"},
            {"s": hm(18),  "e": hm(20),    "act": "dinner_home",    "mode": "stay"},
            {"s": hm(20),  "e": hm(23),    "act": "family_time",    "mode": "stay"},
            {"s": hm(23),  "e": 1440,      "act": "sleep",          "mode": "stay"},
        ]

    if template_id == "shift":   # 工場/飲食/パート — irregular
        return [
            {"s": 0,       "e": hm(7),     "act": "sleep",          "mode": "stay"},
            {"s": hm(7),   "e": hm(8,30),  "act": "morning_routine","mode": "stay"},
            {"s": hm(8,30),"e": hm(13),    "act": "work",           "mode": "stay"},
            {"s": hm(13),  "e": hm(14),    "act": "lunch_home",     "mode": "stay"},
            {"s": hm(14),  "e": hm(19),    "act": "work",           "mode": "stay"},
            {"s": hm(19),  "e": hm(20,30), "act": "dinner_home",    "mode": "stay"},
            {"s": hm(20,30),"e": hm(23),   "act": "leisure",        "mode": "stay"},
            {"s": hm(23),  "e": 1440,      "act": "sleep",          "mode": "stay"},
        ]

    if template_id == "healthcare":   # 看護師: variable, treat as office
        return schedule_template("office", weekend)

    if template_id == "retail":
        return schedule_template("shift", weekend)

    # default
    return schedule_template("office", weekend)
