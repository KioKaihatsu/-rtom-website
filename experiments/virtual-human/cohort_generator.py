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
# 注: 旧版。実 sampling は CITIES の市区町村中心点を使う（海の上を回避）
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

# 各都県の代表市区町村: (label, lat, lng, weight)
# 重みは概ね人口比。座標は市区町村役所/中心駅の実 lat/lng。
CITIES: dict[str, list[tuple[str, float, float, float]]] = {
    "東京都23区": [
        ("千代田", 35.6938, 139.7536, 0.005),
        ("中央",   35.6707, 139.7720, 0.012),
        ("港",     35.6585, 139.7454, 0.022),
        ("新宿",   35.6938, 139.7035, 0.030),
        ("文京",   35.7081, 139.7522, 0.020),
        ("台東",   35.7126, 139.7800, 0.016),
        ("墨田",   35.7106, 139.8014, 0.022),
        ("江東",   35.6730, 139.8174, 0.040),
        ("品川",   35.6092, 139.7302, 0.035),
        ("目黒",   35.6411, 139.6982, 0.024),
        ("大田",   35.5612, 139.7160, 0.060),
        ("世田谷", 35.6464, 139.6533, 0.080),
        ("渋谷",   35.6640, 139.6982, 0.020),
        ("中野",   35.7077, 139.6638, 0.028),
        ("杉並",   35.6995, 139.6364, 0.045),
        ("豊島",   35.7322, 139.7155, 0.025),
        ("北",     35.7528, 139.7340, 0.030),
        ("荒川",   35.7361, 139.7833, 0.018),
        ("板橋",   35.7515, 139.7095, 0.045),
        ("練馬",   35.7359, 139.6517, 0.060),
        ("足立",   35.7755, 139.8045, 0.060),
        ("葛飾",   35.7434, 139.8473, 0.038),
        ("江戸川", 35.7066, 139.8683, 0.050),
    ],
    "東京都市部": [
        ("八王子",   35.6664, 139.3158, 0.030),
        ("立川",     35.6996, 139.4138, 0.015),
        ("武蔵野",   35.7180, 139.5664, 0.012),
        ("三鷹",     35.6839, 139.5598, 0.014),
        ("青梅",     35.7878, 139.2756, 0.010),
        ("府中",     35.6685, 139.4778, 0.018),
        ("昭島",     35.7060, 139.3539, 0.008),
        ("調布",     35.6516, 139.5413, 0.018),
        ("町田",     35.5460, 139.4458, 0.030),
        ("小金井",   35.6997, 139.5044, 0.010),
        ("小平",     35.7286, 139.4773, 0.016),
        ("日野",     35.6717, 139.3950, 0.015),
        ("東村山",   35.7548, 139.4682, 0.012),
        ("国分寺",   35.7106, 139.4624, 0.010),
        ("国立",     35.6839, 139.4413, 0.006),
        ("狛江",     35.6347, 139.5783, 0.006),
        ("東久留米", 35.7587, 139.5285, 0.010),
        ("多摩",     35.6385, 139.4467, 0.012),
        ("稲城",     35.6378, 139.5040, 0.008),
        ("西東京",   35.7252, 139.5384, 0.010),
    ],
    "神奈川県": [
        ("横浜中区",     35.4437, 139.6380, 0.030),
        ("横浜西区",     35.4639, 139.6232, 0.014),
        ("横浜港北",     35.5076, 139.6207, 0.050),
        ("横浜青葉",     35.5612, 139.5378, 0.045),
        ("横浜緑",       35.5135, 139.5418, 0.022),
        ("横浜旭",       35.4767, 139.5667, 0.030),
        ("横浜泉",       35.4135, 139.4877, 0.022),
        ("横浜戸塚",     35.4039, 139.5305, 0.030),
        ("横浜金沢",     35.3414, 139.6228, 0.025),
        ("横浜鶴見",     35.5067, 139.6796, 0.030),
        ("川崎中原",     35.5798, 139.6480, 0.030),
        ("川崎高津",     35.5950, 139.6234, 0.025),
        ("川崎多摩",     35.6189, 139.5814, 0.022),
        ("川崎宮前",     35.5859, 139.5825, 0.025),
        ("川崎麻生",     35.6044, 139.5119, 0.020),
        ("川崎川崎区",   35.5308, 139.7029, 0.022),
        ("相模原中央",   35.5712, 139.3739, 0.040),
        ("相模原南",     35.5331, 139.4429, 0.035),
        ("藤沢",         35.3392, 139.4900, 0.040),
        ("茅ヶ崎",       35.3296, 139.4096, 0.022),
        ("鎌倉",         35.3193, 139.5466, 0.015),
        ("逗子",         35.2967, 139.5777, 0.006),
        ("平塚",         35.3270, 139.3490, 0.025),
        ("厚木",         35.4392, 139.3614, 0.020),
        ("海老名",       35.4456, 139.3911, 0.013),
        ("小田原",       35.2557, 139.1556, 0.018),
        ("大和",         35.4710, 139.4630, 0.020),
        ("秦野",         35.3753, 139.2202, 0.014),
    ],
    "埼玉県": [
        ("さいたま大宮", 35.9081, 139.6285, 0.060),
        ("さいたま浦和", 35.8616, 139.6455, 0.055),
        ("さいたま南",   35.8504, 139.6443, 0.030),
        ("さいたま西",   35.8927, 139.5840, 0.025),
        ("さいたま北",   35.9483, 139.6260, 0.025),
        ("さいたま見沼", 35.9389, 139.6770, 0.025),
        ("川越",         35.9248, 139.4856, 0.040),
        ("川口",         35.8076, 139.7204, 0.060),
        ("所沢",         35.7990, 139.4691, 0.040),
        ("越谷",         35.8911, 139.7900, 0.040),
        ("草加",         35.8260, 139.8049, 0.030),
        ("春日部",       35.9783, 139.7521, 0.025),
        ("上尾",         35.9777, 139.5934, 0.025),
        ("熊谷",         36.1473, 139.3875, 0.025),
        ("狭山",         35.8530, 139.4124, 0.018),
        ("入間",         35.8362, 139.3915, 0.018),
        ("朝霞",         35.7918, 139.5919, 0.020),
        ("新座",         35.7937, 139.5650, 0.018),
        ("和光",         35.7813, 139.6063, 0.012),
        ("戸田",         35.8167, 139.6779, 0.015),
        ("蕨",           35.8252, 139.6863, 0.010),
    ],
    "千葉県": [
        ("千葉中央",     35.6056, 140.1233, 0.040),
        ("千葉花見川",   35.6533, 140.0900, 0.030),
        ("千葉稲毛",     35.6347, 140.0964, 0.028),
        ("船橋",         35.6947, 139.9826, 0.080),
        ("市川",         35.7218, 139.9314, 0.060),
        ("松戸",         35.7785, 139.9039, 0.060),
        ("柏",           35.8623, 139.9706, 0.052),
        ("市原",         35.4983, 140.1156, 0.035),
        ("習志野",       35.6815, 140.0260, 0.025),
        ("浦安",         35.6533, 139.9020, 0.025),
        ("八千代",       35.7233, 140.0973, 0.025),
        ("流山",         35.8567, 139.9020, 0.025),
        ("我孫子",       35.8650, 140.0228, 0.020),
        ("成田",         35.7762, 140.3187, 0.020),
        ("木更津",       35.3766, 139.9242, 0.020),
        ("印西",         35.8312, 140.1474, 0.015),
        ("佐倉",         35.7237, 140.2228, 0.020),
        ("茂原",         35.4282, 140.2882, 0.015),
        ("野田",         35.9550, 139.8761, 0.020),
    ],
    "茨城県": [
        ("水戸",         36.3658, 140.4711, 0.040),
        ("つくば",       36.0834, 140.1117, 0.045),
        ("日立",         36.5993, 140.6510, 0.025),
        ("ひたちなか",   36.3964, 140.5347, 0.025),
        ("土浦",         36.0793, 140.2049, 0.025),
        ("古河",         36.1817, 139.7551, 0.020),
        ("取手",         35.9036, 140.0410, 0.020),
        ("龍ケ崎",       35.9118, 140.1822, 0.015),
        ("守谷",         35.9512, 139.9755, 0.018),
        ("牛久",         35.9777, 140.1418, 0.014),
        ("石岡",         36.1907, 140.2872, 0.015),
        ("下妻",         36.1850, 139.9678, 0.012),
        ("筑西",         36.3070, 139.9831, 0.020),
        ("つくばみらい", 35.9650, 140.0337, 0.013),
    ],
    "栃木県": [
        ("宇都宮",       36.5594, 139.8836, 0.080),
        ("小山",         36.3120, 139.8000, 0.030),
        ("栃木",         36.3814, 139.7320, 0.025),
        ("足利",         36.3409, 139.4499, 0.025),
        ("佐野",         36.3144, 139.5790, 0.022),
        ("鹿沼",         36.5677, 139.7448, 0.020),
        ("日光",         36.7196, 139.6982, 0.015),
        ("那須塩原",     36.9608, 140.0470, 0.018),
        ("真岡",         36.4404, 140.0119, 0.014),
        ("大田原",       36.8728, 140.0167, 0.013),
        ("矢板",         36.8092, 139.9252, 0.010),
        ("さくら",       36.6884, 139.9748, 0.011),
    ],
    "群馬県": [
        ("前橋",         36.3911, 139.0608, 0.050),
        ("高崎",         36.3219, 139.0033, 0.060),
        ("太田",         36.2912, 139.3756, 0.045),
        ("伊勢崎",       36.3140, 139.1976, 0.040),
        ("桐生",         36.4053, 139.3306, 0.022),
        ("渋川",         36.4884, 139.0001, 0.018),
        ("藤岡",         36.2592, 139.0750, 0.020),
        ("富岡",         36.2596, 138.8918, 0.012),
        ("館林",         36.2451, 139.5395, 0.018),
        ("沼田",         36.6453, 139.0445, 0.015),
        ("安中",         36.3265, 138.8884, 0.012),
    ],
}

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
    commute_target_lat: float | None
    commute_target_lng: float | None
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


def _sample_location(rng: random.Random) -> tuple[str, str, float, float]:
    """Pick a (prefecture, city_label, lat, lng) from real city centroids.

    Sample a prefecture by population weight, then a city within it by
    population weight, then jitter the centroid by ~1.5km (≈0.013°).
    This keeps every persona on land (no Tokyo Bay swimmers).
    """
    pref_w = [p[1] for p in PREFECTURES]
    pref = rng.choices(PREFECTURES, weights=pref_w, k=1)[0]
    cities = CITIES[pref[0]]
    city_w = [c[3] for c in cities]
    city = rng.choices(cities, weights=city_w, k=1)[0]
    # ~1.5km radius jitter so multiple personas per city look distributed
    # but still inside the city's land area
    jitter_lat = rng.gauss(0, 0.010)
    jitter_lng = rng.gauss(0, 0.012)
    lat = city[1] + max(-0.02, min(0.02, jitter_lat))
    lng = city[2] + max(-0.025, min(0.025, jitter_lng))
    return pref[0], city[0], lat, lng


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


# Tokyo core / sub-centers for office commute targets
_TOKYO_CORES = [
    (35.6812, 139.7671),   # 東京駅 / 大手町
    (35.6594, 139.7005),   # 渋谷
    (35.6896, 139.7006),   # 新宿
    (35.7295, 139.7110),   # 池袋
    (35.6585, 139.7454),   # 六本木
    (35.6284, 139.7387),   # 品川
]


def _workplace_for(template_id: str, home_lat: float, home_lng: float,
                    rng: random.Random) -> tuple[float | None, float | None]:
    """Workplace coordinates approximation by schedule template.

    - office/healthcare: nearest Tokyo core + jitter
    - wfh: home
    - student: 西早稲田 / 御茶ノ水 / 三田 area
    - retail/shift/home/retired: stays in own neighbourhood
    """
    if template_id == "wfh":
        return (home_lat, home_lng)
    if template_id in ("office", "healthcare"):
        # nearest of the cores
        target = min(_TOKYO_CORES,
                     key=lambda c: (c[0] - home_lat) ** 2 + (c[1] - home_lng) ** 2)
        return (target[0] + rng.uniform(-0.008, 0.008),
                target[1] + rng.uniform(-0.012, 0.012))
    if template_id == "student":
        unis = [(35.7062, 139.7195),  # 早稲田
                (35.7022, 139.7621),  # 御茶ノ水/東大
                (35.6477, 139.7400),  # 三田/慶應
                (35.6754, 139.7600)]  # 麻布
        target = rng.choice(unis)
        return (target[0] + rng.uniform(-0.005, 0.005),
                target[1] + rng.uniform(-0.005, 0.005))
    # shift/retail/home/retired: small local jitter (stays near home)
    return (home_lat + rng.uniform(-0.006, 0.006),
            home_lng + rng.uniform(-0.006, 0.006))


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
        # Land-only location sampling via city centroid + jitter
        pref_name, _city_name, lat, lng = _sample_location(rng)
        prefecture = (pref_name,)  # only the name is used below
        o, c, e, a, neu = _sample_big5(age, rng)
        # Unique-ish names: append index suffix for collisions
        name = _sample_name(gender, rng)
        if name in used_names:
            name = f"{name}_{i}"
        used_names.add(name)
        affinity = _derive_brand_affinity(age, gender, income, o, rng)
        # Workplace approximation by template
        wp_lat, wp_lng = _workplace_for(occ[3], lat, lng, rng)
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
            commute_target_lat=round(wp_lat, 5) if wp_lat is not None else None,
            commute_target_lng=round(wp_lng, 5) if wp_lng is not None else None,
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
