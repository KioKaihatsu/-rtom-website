"""EC 購買イベント生成器。

各仮想人格に対して、当日プラウシブルな購買イベント列（時刻・チャネル・
カテゴリ・SKU・金額）を生成する。生成は人格ごと/日ごとに seed 固定で
決定論的。
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import date as date_t
from typing import Any


# ----------------------------------------------------------------------------
# Channel catalog
# ----------------------------------------------------------------------------

EC_CHANNELS: dict[str, dict[str, Any]] = {
    "Amazon": {
        "categories": ["日用品", "書籍", "電化製品", "食品", "コーヒー", "サブスク"],
        "price_mult": 1.0,
    },
    "楽天市場": {
        "categories": ["食品", "アパレル", "日用品", "化粧品"],
        "price_mult": 1.1,
    },
    "Yahoo!ショッピング": {
        "categories": ["食品", "日用品", "アパレル"],
        "price_mult": 0.9,
    },
    "メルカリ": {
        "categories": ["アパレル", "ホビー", "中古品", "本"],
        "price_mult": 0.4,
    },
    "ZOZOTOWN": {
        "categories": ["アパレル", "シューズ"],
        "price_mult": 1.3,
    },
    "Uniqlo online": {
        "categories": ["アパレル"],
        "price_mult": 0.7,
    },
    "MUJI passport": {
        "categories": ["日用品", "アパレル", "食品", "家具"],
        "price_mult": 0.9,
    },
    "SHEIN": {
        "categories": ["アパレル", "雑貨"],
        "price_mult": 0.3,
    },
    "iHerb": {
        "categories": ["サプリ", "化粧品", "食品"],
        "price_mult": 1.0,
    },
    "BUYMA": {
        "categories": ["ブランド品", "アパレル"],
        "price_mult": 2.5,
    },
    "Apple": {
        "categories": ["電化製品", "アクセサリ", "サブスク"],
        "price_mult": 3.0,
    },
    "Yodobashi.com": {
        "categories": ["電化製品", "ゲーム", "ホビー"],
        "price_mult": 1.1,
    },
    "honto": {
        "categories": ["書籍", "電子書籍"],
        "price_mult": 0.5,
    },
}

CATEGORY_SKUS: dict[str, list[str]] = {
    "日用品": ["トイレットペーパー 12ロール", "洗濯洗剤 詰替", "シャンプー 詰替",
              "ティッシュ 5箱", "歯磨き粉 セット"],
    "書籍": ["小説", "ビジネス書", "技術書", "雑誌 定期購読"],
    "電子書籍": ["Kindle 小説", "Kindle 漫画 1巻"],
    "電化製品": ["イヤホン", "USB-Cハブ", "Bluetoothスピーカー",
                "ワイヤレス充電器", "モニターアーム"],
    "食品": ["コーヒー豆 200g", "オーガニックパスタ", "プロテイン 1kg",
            "オイル セット", "缶詰アソート"],
    "コーヒー": ["スターバックス豆 250g", "ブルーボトル ドリップ 6個",
                "猿田彦珈琲 ドリップバッグ"],
    "アパレル": ["Tシャツ", "ニット", "ジーンズ", "スニーカー",
                "ジャケット", "ワンピース", "コート"],
    "化粧品": ["リップ", "ファンデーション", "美容液", "マスカラ",
              "アイシャドウパレット"],
    "シューズ": ["スニーカー", "革靴", "ヒール"],
    "サプリ": ["ビタミンC", "プロテイン", "オメガ3", "鉄分"],
    "ホビー": ["プラモデル", "フィギュア", "コレクションカード", "パズル"],
    "中古品": ["古着アウター", "ヴィンテージTシャツ", "中古本",
              "古着ニット"],
    "本": ["小説", "雑誌バックナンバー"],
    "ブランド品": ["ハンドバッグ", "腕時計", "サングラス", "財布"],
    "アクセサリ": ["AirPods Pro", "Apple Watch バンド", "MagSafe充電器"],
    "サブスク": ["Netflix プレミアム", "Amazon Prime", "Spotify",
                "Apple One", "Kindle Unlimited"],
    "家具": ["クッション", "収納ボックス", "ラグ", "デスクライト"],
    "雑貨": ["スマホケース", "ステッカーセット", "アクセサリ"],
    "ゲーム": ["Switch ソフト", "PS5 ソフト", "Steam キー"],
}


# ----------------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Purchase:
    minute: int       # minute-of-day, 0..1439
    channel: str
    category: str
    sku: str
    price_jpy: int
    impulse: bool     # True if triggered by leisure/SNS, False if planned

    def to_dict(self) -> dict[str, Any]:
        return {
            "m": self.minute,
            "ch": self.channel,
            "cat": self.category,
            "sku": self.sku,
            "p": self.price_jpy,
            "imp": self.impulse,
        }


def _seed_for(name: str, target_date: date_t) -> int:
    h = hashlib.sha256(f"{name}|{target_date.isoformat()}".encode()).digest()
    return int.from_bytes(h[:4], "big")


def _frequency(persona) -> int:
    """Plausible purchase count today (0-12)."""
    t = persona.traits
    base = t.brand_affinity.get("Amazon", 0.4) * 7  # 0..7
    if t.age >= 60:
        base *= 0.4
    if t.openness >= 0.7:
        base *= 1.25
    if t.work_from_home:
        base *= 1.15  # more screen time
    # Day-to-day variation
    return max(0, min(12, round(base)))


def _eligible_channels(persona) -> list[tuple[str, float]]:
    t = persona.traits
    age = t.age
    income = t.income_jpy_year
    aff = t.brand_affinity
    out: list[tuple[str, float]] = []

    out.append(("Amazon", aff.get("Amazon", 0.4)))
    out.append(("楽天市場", 0.6 if 28 <= age <= 55 else 0.2))
    out.append(("Yahoo!ショッピング", 0.45 if age >= 45 else 0.15))
    out.append(("メルカリ", 0.55 if 18 <= age <= 35 else 0.15))
    out.append(("Uniqlo online", aff.get("Uniqlo", 0.4)))
    out.append(("MUJI passport", aff.get("MUJI", 0.3)))
    out.append(("honto", 0.30 if age >= 40 else 0.10))

    if 18 <= age <= 35:
        out.append(("ZOZOTOWN",
                    aff.get("ZARA", 0.3) + aff.get("Uniqlo", 0.3) * 0.5))
    if age <= 22:
        out.append(("SHEIN", 0.70))
    if t.gender == "female" or age <= 35:
        out.append(("iHerb", 0.25))
    if income >= 7_000_000:
        out.append(("BUYMA", 0.30))
    if t.openness >= 0.65 and income >= 5_000_000:
        out.append(("Apple", 0.40))
    if t.openness >= 0.55 and age <= 45:
        out.append(("Yodobashi.com", 0.30))
    return out


_HIGH_PROPENSITY_ACTS = {
    "leisure", "instagram_scroll", "wind_down", "tv_time",
    "family_time", "breakfast_home", "dinner_home", "study_home",
    "hobby",
}
_MED_PROPENSITY_ACTS = {
    "morning_routine", "morning_routine_w_baby", "morning_routine_w_kids",
    "errands", "errands_home", "childcare", "housework",
    "lunch_home", "lunch_home_w_kids",
}
_WORK_ACTS = {"work", "wfh_work"}


def _purchase_timing(schedule_segments: list[dict], rng: random.Random) -> int:
    """Pick a minute-of-day where the persona is plausibly online shopping."""
    weighted: list[tuple[int, int]] = []
    for seg in schedule_segments:
        if seg["act"] == "sleep":
            continue
        if seg["mode"] == "train":
            w = 4
        elif seg["act"] in _HIGH_PROPENSITY_ACTS:
            w = 6
        elif seg["act"] in _MED_PROPENSITY_ACTS:
            w = 2
        elif seg["act"] in _WORK_ACTS:
            w = 1  # 仕事中こっそり
        else:
            w = 0
        if w > 0:
            for m in range(seg["s"], seg["e"], 5):
                weighted.append((m, w))
    if not weighted:
        return rng.randint(8 * 60, 22 * 60)
    minutes, weights = zip(*weighted)
    return rng.choices(minutes, weights=weights, k=1)[0]


def _impulse_at(segments: list[dict], minute: int) -> bool:
    for seg in segments:
        if seg["s"] <= minute < seg["e"]:
            return seg["act"] in {
                "instagram_scroll", "tv_time", "leisure", "wind_down",
            } or seg["mode"] == "train"
    return False


def generate_purchases(
    persona, schedule_segments: list[dict], target_date: date_t
) -> list[Purchase]:
    """Return today's purchase events for `persona`."""
    seed = _seed_for(persona.traits.name, target_date)
    rng = random.Random(seed)
    n = _frequency(persona)
    if n == 0:
        return []

    channels = _eligible_channels(persona)
    if not channels:
        return []
    ch_names, ch_weights = zip(*channels)

    t = persona.traits
    income = t.income_jpy_year
    base_price = (
        1200 if income < 4_000_000
        else 2800 if income < 7_000_000
        else 5500
    )

    purchases: list[Purchase] = []
    used_minutes: set[int] = set()
    for _ in range(n):
        channel = rng.choices(ch_names, weights=ch_weights, k=1)[0]
        info = EC_CHANNELS[channel]
        category = rng.choice(info["categories"])
        sku = rng.choice(CATEGORY_SKUS.get(category, [category]))
        price = int(base_price * info["price_mult"] * rng.uniform(0.4, 2.2))
        price = max(180, (price // 10) * 10)

        # Time with collision avoidance
        for _try in range(8):
            minute = _purchase_timing(schedule_segments, rng)
            if minute not in used_minutes:
                break
        used_minutes.add(minute)

        purchases.append(Purchase(
            minute=minute,
            channel=channel,
            category=category,
            sku=sku,
            price_jpy=price,
            impulse=_impulse_at(schedule_segments, minute),
        ))

    purchases.sort(key=lambda p: p.minute)
    return purchases
