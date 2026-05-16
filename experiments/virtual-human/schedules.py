"""Daily schedules for the 12-persona cohort.

Each persona's daily timetable is expressed as a list of segments. Given the
current wall-clock minute, the monitor looks up which segment is active
and (for transit segments) interpolates along the polyline. No future
events are pre-computed beyond defining the timetable.

Mode strings used by the frontend:
    stay   = at a single place (sleep/work/eat/etc)
    walk   = on foot, ~5km/h
    train  = on rail, polyline = sequence of station coords
    bus    = on a bus route
    car    = personal vehicle
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from routes import STN, YAMANOTE_KOMAGOME_TO_TOKYO, \
    YAMANOTE_KOMAGOME_TO_SHIBUYA, DENENTOSHI_SANGENJAYA_TO_SHIBUYA, \
    KEIHIN_AKABANE_TO_OJI


Mode = Literal["stay", "walk", "train", "bus", "car"]
LatLng = tuple[float, float]


@dataclass(frozen=True)
class Segment:
    start_min: int
    end_min: int
    activity: str        # e.g. "sleep", "work", "commute", "lunch", "shop"
    mode: Mode
    place_name: str
    waypoints: list[LatLng]
    cost_jpy: int = 0
    wage_jpy: int = 0       # earned during this whole segment (not per hour)
    touchpoint: dict | None = None  # {"channel": ..., "brand": ...} or None

    @property
    def duration_min(self) -> int:
        return self.end_min - self.start_min

    def position_at(self, minute: int) -> LatLng:
        if minute <= self.start_min:
            return self.waypoints[0]
        if minute >= self.end_min:
            return self.waypoints[-1]
        if len(self.waypoints) == 1:
            return self.waypoints[0]
        # Linear interpolation along polyline by time fraction.
        f = (minute - self.start_min) / max(1, self.duration_min)
        # Total polyline length parameter from 0..1, with each segment equal weight.
        n = len(self.waypoints) - 1
        seg_idx = min(int(f * n), n - 1)
        seg_f = (f * n) - seg_idx
        a = self.waypoints[seg_idx]
        b = self.waypoints[seg_idx + 1]
        return (a[0] + (b[0] - a[0]) * seg_f, a[1] + (b[1] - a[1]) * seg_f)


def hm(h: int, m: int = 0) -> int:
    return h * 60 + m


# ============================================================================
# Helper builders
# ============================================================================

def _stay(start: int, end: int, activity: str, name: str,
          pos: LatLng, cost: int = 0, wage: int = 0,
          tp: dict | None = None) -> Segment:
    return Segment(start, end, activity, "stay", name, [pos],
                   cost_jpy=cost, wage_jpy=wage, touchpoint=tp)


def _move(start: int, end: int, activity: str, mode: Mode, name: str,
          path: list[LatLng], cost: int = 0) -> Segment:
    return Segment(start, end, activity, mode, name, list(path), cost_jpy=cost)


# ============================================================================
# Per-persona schedule generators
# ============================================================================

# 1. 田中 浩二 (45 銀行員) — 駒込→大手町
def tanaka(home: LatLng, weekend: bool) -> list[Segment]:
    if weekend:
        return [
            _stay(0,   hm(7,30),  "sleep", "自宅", home),
            _stay(hm(7,30), hm(8,30), "morning_routine", "自宅", home),
            _stay(hm(8,30), hm(10), "family_time", "自宅", home),
            _move(hm(10), hm(10,8), "walk", "walk", "→霜降銀座",
                  [home, STN["komagome"], (35.7414, 139.7448)]),
            _stay(hm(10,8), hm(11), "shimofuri_grocery", "霜降銀座商店街",
                  (35.7414, 139.7448), cost=1600,
                  tp={"channel": "霜降銀座", "brand": None}),
            _move(hm(11), hm(11,10), "walk", "walk", "→自宅",
                  [(35.7414, 139.7448), STN["komagome"], home]),
            _stay(hm(11,10), hm(13), "lunch_home", "自宅", home),
            _stay(hm(13), hm(17), "leisure", "自宅", home),
            _move(hm(17), hm(17,12), "walk", "walk", "→Riverbed",
                  [home, STN["komagome"], (35.7418, 139.7445)]),
            _stay(hm(17,12), hm(19), "shimofuri_dining", "Riverbed in Otherworld",
                  (35.7418, 139.7445), cost=3500,
                  tp={"channel": "霜降銀座", "brand": "Riverbed in Otherworld"}),
            _move(hm(19), hm(19,8), "walk", "walk", "→自宅",
                  [(35.7418, 139.7445), STN["komagome"], home]),
            _stay(hm(19,8), hm(22,30), "leisure", "自宅", home),
            _stay(hm(22,30), hm(23,30), "wind_down", "自宅", home),
            _stay(hm(23,30), 1440, "sleep", "自宅", home),
        ]
    # Weekday: 駒込 → 大手町
    walk_to_komagome = [home, STN["komagome"]]
    train_path = YAMANOTE_KOMAGOME_TO_TOKYO
    walk_to_office = [STN["tokyo"], STN["otemachi_bank"]]
    walk_back = [STN["otemachi_bank"], STN["tokyo"]]
    train_back = list(reversed(YAMANOTE_KOMAGOME_TO_TOKYO))
    walk_home = [STN["komagome"], home]
    return [
        _stay(0,   hm(6,30),  "sleep", "自宅", home),
        _stay(hm(6,30), hm(7,15), "morning_routine", "自宅", home),
        _move(hm(7,15), hm(7,20), "walk", "walk", "→駒込駅", walk_to_komagome),
        _move(hm(7,20), hm(7,45), "train", "train", "山手線 駒込→東京",
              train_path, cost=220),
        _move(hm(7,45), hm(7,55), "walk", "walk", "→大手町オフィス", walk_to_office),
        _stay(hm(7,55), hm(12), "work", "メガバンク 大手町",
              STN["otemachi_bank"], wage=17400),  # 4hr * 4250
        _stay(hm(12), hm(13), "lunch_out", "丸の内ランチ",
              (35.6840, 139.7650), cost=1200),
        _stay(hm(13), hm(18), "work", "メガバンク 大手町",
              STN["otemachi_bank"], wage=21250),
        _move(hm(18), hm(18,8), "walk", "walk", "→東京駅", walk_back),
        _move(hm(18,8), hm(18,33), "train", "train", "山手線 東京→駒込",
              train_back, cost=220),
        _move(hm(18,33), hm(18,38), "walk", "walk", "→自宅", walk_home),
        _stay(hm(18,38), hm(20), "dinner_home", "自宅", home),
        _stay(hm(20), hm(22,30), "family_time", "自宅", home),
        _stay(hm(22,30), hm(23), "wind_down", "自宅", home),
        _stay(hm(23), 1440, "sleep", "自宅", home),
    ]


# 2. 山本 結衣 (32 看護師) — 巣鴨→駒込病院, NIGHT SHIFT today
def yamamoto(home: LatLng, weekend: bool, night_shift_today: bool) -> list[Segment]:
    hospital = STN["komagome_hospital"]
    if night_shift_today:
        # 前夜17:00から夜勤入り、本日は朝まで勤務、その後睡眠
        return [
            _stay(0, hm(8,30), "night_shift", "都立駒込病院 病棟",
                  hospital, wage=15000),  # 8.5h * ~1800
            _move(hm(8,30), hm(8,42), "walk", "walk", "→駒込駅",
                  [hospital, STN["komagome"]]),
            _move(hm(8,42), hm(8,46), "train", "train", "山手線 駒込→巣鴨",
                  [STN["komagome"], STN["sugamo"]], cost=140),
            _move(hm(8,46), hm(8,55), "walk", "walk", "→自宅",
                  [STN["sugamo"], home]),
            _stay(hm(8,55), hm(9,30), "breakfast_home", "自宅", home),
            _stay(hm(9,30), hm(16), "sleep", "自宅", home),  # 昼寝
            _stay(hm(16), hm(17,30), "leisure", "自宅", home),
            _move(hm(17,30), hm(17,40), "walk", "walk", "→霜降銀座",
                  [home, STN["sugamo"], (35.7414, 139.7448)]),
            _stay(hm(17,40), hm(18,30), "shimofuri_dining",
                  "Riverbed in Otherworld", (35.7418, 139.7445), cost=2800,
                  tp={"channel": "霜降銀座", "brand": "Riverbed in Otherworld"}),
            _move(hm(18,30), hm(18,40), "walk", "walk", "→自宅",
                  [(35.7418, 139.7445), STN["sugamo"], home]),
            _stay(hm(18,40), hm(21,30), "leisure", "自宅", home),
            _stay(hm(21,30), hm(23), "wind_down", "自宅", home),
            _stay(hm(23), 1440, "sleep", "自宅", home),
        ]
    if weekend:
        return [
            _stay(0, hm(8), "sleep", "自宅", home),
            _stay(hm(8), hm(10), "morning_routine", "自宅", home),
            _stay(hm(10), hm(12), "leisure", "自宅", home),
            _stay(hm(12), hm(13), "lunch_home", "自宅", home),
            _stay(hm(13), hm(17), "leisure", "自宅", home),
            _move(hm(17), hm(17,15), "walk", "walk", "→霜降銀座",
                  [home, STN["sugamo"], (35.7414, 139.7448)]),
            _stay(hm(17,15), hm(18,30), "shimofuri_dining",
                  "Riverbed in Otherworld", (35.7418, 139.7445), cost=2800,
                  tp={"channel": "霜降銀座", "brand": "Riverbed in Otherworld"}),
            _move(hm(18,30), hm(18,45), "walk", "walk", "→自宅",
                  [(35.7418, 139.7445), STN["sugamo"], home]),
            _stay(hm(18,45), hm(23), "leisure", "自宅", home),
            _stay(hm(23), 1440, "sleep", "自宅", home),
        ]
    # 平日 day shift
    return [
        _stay(0, hm(6,30), "sleep", "自宅", home),
        _stay(hm(6,30), hm(7,15), "morning_routine", "自宅", home),
        _move(hm(7,15), hm(7,25), "walk", "walk", "→巣鴨駅",
              [home, STN["sugamo"]]),
        _move(hm(7,25), hm(7,29), "train", "train", "山手線 巣鴨→駒込",
              [STN["sugamo"], STN["komagome"]], cost=140),
        _move(hm(7,29), hm(7,40), "walk", "walk", "→駒込病院",
              [STN["komagome"], hospital]),
        _stay(hm(7,40), hm(12), "work", "都立駒込病院",
              hospital, wage=10800),
        _stay(hm(12), hm(13), "lunch_konbini", "病院近くコンビニ",
              (35.7370, 139.7475), cost=650),
        _stay(hm(13), hm(17), "work", "都立駒込病院",
              hospital, wage=12000),
        _move(hm(17), hm(17,15), "walk", "walk", "→自宅",
              [hospital, STN["komagome"], STN["sugamo"], home]),
        _stay(hm(17,15), hm(19), "dinner_home", "自宅", home),
        _stay(hm(19), hm(23), "leisure", "自宅", home),
        _stay(hm(23), 1440, "sleep", "自宅", home),
    ]


# 3. 小林 章 (68 退職)
def kobayashi(home: LatLng, weekend: bool) -> list[Segment]:
    rio = (35.7418, 139.7445)
    return [
        _stay(0, hm(6,30), "sleep", "自宅", home),
        _stay(hm(6,30), hm(8), "morning_routine", "自宅", home),
        _move(hm(8), hm(8,15), "walk", "walk", "→霜降銀座 朝散歩",
              [home, STN["tabata"], (35.7414, 139.7448)]),
        _stay(hm(8,15), hm(9,15), "shimofuri_stroll", "霜降銀座商店街",
              (35.7414, 139.7448),
              tp={"channel": "霜降銀座", "brand": None}),
        _move(hm(9,15), hm(9,30), "walk", "walk", "→自宅",
              [(35.7414, 139.7448), STN["tabata"], home]),
        _stay(hm(9,30), hm(12), "leisure", "自宅", home),
        _stay(hm(12), hm(13), "lunch_home", "自宅", home),
        _stay(hm(13), hm(17), "leisure", "自宅", home),
        _move(hm(17), hm(17,15), "walk", "walk", "→Riverbed",
              [home, STN["tabata"], rio]),
        _stay(hm(17,15), hm(18,45), "shimofuri_dining",
              "Riverbed in Otherworld", rio, cost=3200,
              tp={"channel": "霜降銀座", "brand": "Riverbed in Otherworld"}),
        _move(hm(18,45), hm(19), "walk", "walk", "→自宅",
              [rio, STN["tabata"], home]),
        _stay(hm(19), hm(22), "tv_time", "自宅", home),
        _stay(hm(22), 1440, "sleep", "自宅", home),
    ]


# 4. 鈴木 芽依 (24 美容師) — 池袋徒歩
def suzuki(home: LatLng, weekend: bool) -> list[Segment]:
    salon = STN["ikebukuro_salon"]
    if weekend:
        # 美容室は土日も営業
        return [
            _stay(0, hm(8), "sleep", "自宅", home),
            _stay(hm(8), hm(9), "morning_routine", "自宅", home),
            _move(hm(9), hm(9,15), "walk", "walk", "→美容室",
                  [home, salon]),
            _stay(hm(9,15), hm(13), "work", "美容室 池袋", salon, wage=5400),
            _stay(hm(13), hm(14), "lunch_konbini", "池袋コンビニ",
                  (35.7320, 139.7160), cost=650),
            _stay(hm(14), hm(19), "work", "美容室 池袋", salon, wage=6750),
            _move(hm(19), hm(19,15), "walk", "walk", "→自宅", [salon, home]),
            _stay(hm(19,15), hm(20,30), "dinner_home", "自宅", home),
            _stay(hm(20,30), hm(23,30), "instagram_scroll", "自宅", home,
                  tp={"channel": "Instagram", "brand": None}),
            _stay(hm(23,30), 1440, "sleep", "自宅", home),
        ]
    # 平日も同様だが定休日なら寝てる; ここでは月曜定休と仮定
    is_monday_off = False  # 簡略化
    if is_monday_off:
        return [_stay(0, 1440, "sleep_in", "自宅", home)]
    return [
        _stay(0, hm(8), "sleep", "自宅", home),
        _stay(hm(8), hm(9,30), "morning_routine", "自宅", home),
        _move(hm(9,30), hm(9,45), "walk", "walk", "→美容室", [home, salon]),
        _stay(hm(9,45), hm(13), "work", "美容室 池袋", salon, wage=4400),
        _stay(hm(13), hm(14), "lunch_konbini", "池袋コンビニ",
              (35.7320, 139.7160), cost=650),
        _stay(hm(14), hm(20), "work", "美容室 池袋", salon, wage=8100),
        _move(hm(20), hm(20,15), "walk", "walk", "→自宅", [salon, home]),
        _stay(hm(20,15), hm(21,30), "dinner_home", "自宅", home),
        _stay(hm(21,30), hm(23,30), "leisure", "自宅", home),
        _stay(hm(23,30), 1440, "sleep", "自宅", home),
    ]


# 5. 渡辺 健 (38 リモートエンジニア) — 千石
def watanabe(home: LatLng, weekend: bool) -> list[Segment]:
    rio = (35.7418, 139.7445)
    if weekend:
        return [
            _stay(0, hm(8,30), "sleep", "自宅", home),
            _stay(hm(8,30), hm(10), "morning_routine", "自宅", home),
            _stay(hm(10), hm(12), "hobby", "自宅", home),
            _stay(hm(12), hm(13), "lunch_home", "自宅", home),
            _stay(hm(13), hm(17), "leisure", "自宅", home),
            _move(hm(17), hm(17,20), "walk", "walk", "→Riverbed",
                  [home, STN["sengoku"], (35.7414, 139.7448), rio]),
            _stay(hm(17,20), hm(19), "shimofuri_dining",
                  "Riverbed in Otherworld", rio, cost=3500,
                  tp={"channel": "霜降銀座", "brand": "Riverbed in Otherworld"}),
            _move(hm(19), hm(19,20), "walk", "walk", "→自宅",
                  [rio, STN["sengoku"], home]),
            _stay(hm(19,20), hm(23), "leisure", "自宅", home),
            _stay(hm(23), 1440, "sleep", "自宅", home),
        ]
    return [
        _stay(0, hm(7,30), "sleep", "自宅", home),
        _stay(hm(7,30), hm(9), "morning_routine", "自宅", home),
        _stay(hm(9), hm(12), "wfh_work", "自宅", home, wage=14250),
        _stay(hm(12), hm(13), "lunch_home", "自宅", home),
        _stay(hm(13), hm(18), "wfh_work", "自宅", home, wage=23750),
        _stay(hm(18), hm(19,30), "dinner_home", "自宅", home),
        _stay(hm(19,30), hm(23), "leisure", "自宅", home),
        _stay(hm(23), 1440, "sleep", "自宅", home),
    ]


# 6. 伊藤 桜 (29 フリーランス・王子)
def ito(home: LatLng, weekend: bool) -> list[Segment]:
    return [
        _stay(0, hm(8), "sleep", "自宅", home),
        _stay(hm(8), hm(10), "morning_routine", "自宅", home),
        _stay(hm(10), hm(13), "wfh_work", "自宅", home, wage=6300),
        _stay(hm(13), hm(14), "lunch_home", "自宅", home),
        _move(hm(14), hm(14,15), "walk", "walk", "→霜降銀座カフェ",
              [home, STN["oji"], (35.7414, 139.7448)]),
        _stay(hm(14,15), hm(16,30), "wfh_work", "霜降銀座カフェ",
              (35.7414, 139.7448), wage=4730, cost=580,
              tp={"channel": "霜降銀座", "brand": None}),
        _move(hm(16,30), hm(16,45), "walk", "walk", "→自宅",
              [(35.7414, 139.7448), STN["oji"], home]),
        _stay(hm(16,45), hm(19), "leisure", "自宅", home),
        _stay(hm(19), hm(20,30), "dinner_home", "自宅", home),
        _stay(hm(20,30), hm(23,30), "leisure", "自宅", home),
        _stay(hm(23,30), 1440, "sleep", "自宅", home),
    ]


# 7. 中村 大輔 (52 居酒屋店主) — 大山徒歩, 土曜営業夜
def nakamura(home: LatLng, weekend: bool) -> list[Segment]:
    izakaya = STN["oyama_izakaya"]
    if weekend:
        # 土曜は通常営業: 16:00開店, 24:00閉店, 帰宅は深夜
        return [
            _stay(0, hm(1), "shop_cleanup", "中村屋 (大山)", izakaya, wage=0),
            _move(hm(1), hm(1,10), "walk", "walk", "→自宅", [izakaya, home]),
            _stay(hm(1,10), hm(9), "sleep", "自宅", home),
            _stay(hm(9), hm(11), "morning_routine", "自宅", home),
            _stay(hm(11), hm(13), "errands", "自宅", home),
            _move(hm(13), hm(13,20), "car", "car", "→豊洲市場へ仕入れ",
                  [home, (35.6550, 139.7900)]),
            _stay(hm(13,20), hm(15), "shopping_supply", "豊洲市場",
                  (35.6550, 139.7900), cost=24000),
            _move(hm(15), hm(15,30), "car", "car", "→中村屋",
                  [(35.6550, 139.7900), izakaya]),
            _stay(hm(15,30), hm(16), "shop_prep", "中村屋", izakaya),
            _stay(hm(16), 1440, "work_shop", "中村屋 営業中", izakaya,
                  wage=18000),  # 18-24時の営業利益見込み
        ]
    return [
        _stay(0, hm(1), "shop_cleanup", "中村屋", izakaya, wage=0),
        _move(hm(1), hm(1,10), "walk", "walk", "→自宅", [izakaya, home]),
        _stay(hm(1,10), hm(9), "sleep", "自宅", home),
        _stay(hm(9), hm(11), "morning_routine", "自宅", home),
        _stay(hm(11), hm(15), "errands_home", "自宅", home),
        _move(hm(15), hm(15,10), "walk", "walk", "→中村屋", [home, izakaya]),
        _stay(hm(15,10), hm(16), "shop_prep", "中村屋", izakaya),
        _stay(hm(16), 1440, "work_shop", "中村屋 営業中", izakaya, wage=16000),
    ]


# 8. 高橋 葵 (19 大学生) — 高田馬場→早稲田徒歩
def takahashi(home: LatLng, weekend: bool) -> list[Segment]:
    waseda = STN["waseda_campus"]
    if weekend:
        return [
            _stay(0, hm(11), "sleep", "自宅", home),  # 大学生らしく遅寝坊
            _stay(hm(11), hm(12), "morning_routine", "自宅", home),
            _stay(hm(12), hm(13), "lunch_home", "自宅", home),
            _move(hm(13), hm(13,15), "walk", "walk", "→渋谷へ",
                  [home, STN["takadanobaba"]]),
            _move(hm(13,15), hm(13,35), "train", "train",
                  "山手線 高田馬場→渋谷",
                  [STN["takadanobaba"], STN["shinokubo"], STN["shinjuku"],
                   STN["yoyogi"], STN["harajuku"], STN["shibuya"]], cost=170),
            _stay(hm(13,35), hm(17), "shopping_apparel", "渋谷",
                  STN["shibuya"], cost=4800,
                  tp={"channel": "店舗", "brand": "ZARA"}),
            _move(hm(17), hm(17,25), "train", "train",
                  "山手線 渋谷→高田馬場",
                  [STN["shibuya"], STN["harajuku"], STN["yoyogi"],
                   STN["shinjuku"], STN["shinokubo"], STN["takadanobaba"]],
                  cost=170),
            _move(hm(17,25), hm(17,40), "walk", "walk", "→自宅",
                  [STN["takadanobaba"], home]),
            _stay(hm(17,40), hm(20), "instagram_scroll", "自宅", home,
                  tp={"channel": "TikTok", "brand": None}),
            _stay(hm(20), hm(21), "dinner_home", "自宅", home, cost=400),
            _stay(hm(21), hm(25*60 if False else 1440),
                  "study_night", "自宅", home),
        ]
    # 平日: 大学
    return [
        _stay(0, hm(8), "sleep", "自宅", home),
        _stay(hm(8), hm(9), "morning_routine", "自宅", home),
        _move(hm(9), hm(9,20), "walk", "walk", "→早稲田大学",
              [home, STN["takadanobaba"], waseda]),
        _stay(hm(9,20), hm(12,30), "class", "早稲田大学", waseda),
        _stay(hm(12,30), hm(13,30), "lunch_konbini", "学食",
              waseda, cost=600),
        _stay(hm(13,30), hm(16,30), "class", "早稲田大学", waseda),
        _move(hm(16,30), hm(16,50), "walk", "walk", "→自宅",
              [waseda, STN["takadanobaba"], home]),
        _stay(hm(16,50), hm(19), "study_home", "自宅", home),
        _stay(hm(19), hm(20), "dinner_home", "自宅", home),
        _stay(hm(20), hm(24), "leisure", "自宅", home,
              tp={"channel": "TikTok", "brand": None}),
        _stay(hm(24), 1440, "sleep", "自宅", home),
    ]


# 9. 佐藤 美咲 (29 広告代理店) — 三軒茶屋→渋谷
def sato(home: LatLng, weekend: bool) -> list[Segment]:
    office = STN["shibuya_office"]
    if weekend:
        return [
            _stay(0, hm(9), "sleep", "自宅", home),
            _stay(hm(9), hm(10,30), "morning_routine", "自宅", home),
            _stay(hm(10,30), hm(12), "leisure", "自宅", home),
            _stay(hm(12), hm(13), "lunch_home", "自宅", home),
            _move(hm(13), hm(13,30), "train", "train",
                  "田園都市線 三軒茶屋→渋谷",
                  DENENTOSHI_SANGENJAYA_TO_SHIBUYA, cost=170),
            _stay(hm(13,30), hm(18), "shopping_apparel", "渋谷",
                  STN["shibuya"], cost=12500,
                  tp={"channel": "店舗", "brand": "ZARA"}),
            _move(hm(18), hm(18,30), "train", "train",
                  "田園都市線 渋谷→三軒茶屋",
                  list(reversed(DENENTOSHI_SANGENJAYA_TO_SHIBUYA)), cost=170),
            _move(hm(18,30), hm(18,40), "walk", "walk", "→自宅",
                  [STN["sangenjaya"], home]),
            _stay(hm(18,40), hm(20), "dinner_home", "自宅", home),
            _stay(hm(20), hm(23,30), "leisure", "自宅", home,
                  tp={"channel": "Instagram", "brand": None}),
            _stay(hm(23,30), 1440, "sleep", "自宅", home),
        ]
    return [
        _stay(0, hm(7), "sleep", "自宅", home),
        _stay(hm(7), hm(8,15), "morning_routine", "自宅", home),
        _move(hm(8,15), hm(8,25), "walk", "walk", "→三軒茶屋駅",
              [home, STN["sangenjaya"]]),
        _move(hm(8,25), hm(8,55), "train", "train",
              "田園都市線 三軒茶屋→渋谷",
              DENENTOSHI_SANGENJAYA_TO_SHIBUYA, cost=170),
        _move(hm(8,55), hm(9,5), "walk", "walk", "→渋谷オフィス",
              [STN["shibuya"], office]),
        _stay(hm(9,5), hm(12,30), "work", "広告代理店 渋谷",
              office, wage=8800),
        _stay(hm(12,30), hm(13,30), "lunch_out", "渋谷ランチ",
              (35.6594, 139.7000), cost=1400,
              tp={"channel": "店舗", "brand": "Blue Bottle"}),
        _stay(hm(13,30), hm(19), "work", "広告代理店 渋谷",
              office, wage=13750),
        _move(hm(19), hm(19,30), "train", "train",
              "田園都市線 渋谷→三軒茶屋",
              list(reversed(DENENTOSHI_SANGENJAYA_TO_SHIBUYA)), cost=170),
        _move(hm(19,30), hm(19,45), "walk", "walk", "→自宅",
              [STN["sangenjaya"], home]),
        _stay(hm(19,45), hm(20,30), "dinner_home", "自宅", home),
        _stay(hm(20,30), hm(23,30), "leisure", "自宅", home),
        _stay(hm(23,30), 1440, "sleep", "自宅", home),
    ]


# 10. 林 涼 (35 公務員) — 赤羽→王子（北区役所）
def hayashi(home: LatLng, weekend: bool) -> list[Segment]:
    office = STN["kita_ward"]
    if weekend:
        return [
            _stay(0, hm(7,30), "sleep", "自宅", home),
            _stay(hm(7,30), hm(9), "morning_routine_w_baby", "自宅", home),
            _stay(hm(9), hm(11), "childcare", "自宅", home),
            _move(hm(11), hm(11,10), "walk", "walk", "→赤羽スーパー",
                  [home, (35.7785, 139.7212)]),
            _stay(hm(11,10), hm(12), "grocery", "赤羽スーパー",
                  (35.7785, 139.7212), cost=2400,
                  tp={"channel": "店舗", "brand": None}),
            _move(hm(12), hm(12,10), "walk", "walk", "→自宅",
                  [(35.7785, 139.7212), home]),
            _stay(hm(12,10), hm(13), "lunch_home", "自宅", home),
            _stay(hm(13), hm(17,30), "childcare", "自宅", home),
            _stay(hm(17,30), hm(19), "dinner_home", "自宅", home),
            _stay(hm(19), hm(22,30), "family_time", "自宅", home),
            _stay(hm(22,30), 1440, "sleep", "自宅", home),
        ]
    return [
        _stay(0, hm(6,30), "sleep", "自宅", home),
        _stay(hm(6,30), hm(7,30), "morning_routine_w_baby", "自宅", home),
        _move(hm(7,30), hm(7,42), "walk", "walk", "→赤羽駅", [home, STN["akabane"]]),
        _move(hm(7,42), hm(7,52), "train", "train", "京浜東北線 赤羽→王子",
              KEIHIN_AKABANE_TO_OJI, cost=170),
        _move(hm(7,52), hm(8), "walk", "walk", "→北区役所",
              [STN["oji"], office]),
        _stay(hm(8), hm(12), "work", "北区役所", office, wage=12100),
        _stay(hm(12), hm(13), "lunch_konbini", "区役所近くコンビニ",
              (35.7530, 139.7340), cost=600),
        _stay(hm(13), hm(17,15), "work", "北区役所", office, wage=12850),
        _move(hm(17,15), hm(17,25), "walk", "walk", "→王子駅",
              [office, STN["oji"]]),
        _move(hm(17,25), hm(17,35), "train", "train",
              "京浜東北線 王子→赤羽",
              list(reversed(KEIHIN_AKABANE_TO_OJI)), cost=170),
        _move(hm(17,35), hm(17,47), "walk", "walk", "→自宅",
              [STN["akabane"], home]),
        _stay(hm(17,47), hm(19,30), "childcare", "自宅", home),
        _stay(hm(19,30), hm(20,30), "dinner_home", "自宅", home),
        _stay(hm(20,30), hm(22,30), "family_time", "自宅", home),
        _stay(hm(22,30), 1440, "sleep", "自宅", home),
    ]


# 11. 森 花 (41 主婦) — 西日暮里
def mori(home: LatLng, weekend: bool) -> list[Segment]:
    rio = (35.7418, 139.7445)
    return [
        _stay(0, hm(6,30), "sleep", "自宅", home),
        _stay(hm(6,30), hm(8,30), "morning_routine_w_kids", "自宅", home),
        _stay(hm(8,30), hm(10), "housework", "自宅", home),
        _move(hm(10), hm(10,15), "walk", "walk", "→西日暮里スーパー",
              [home, (35.7327, 139.7660)]),
        _stay(hm(10,15), hm(11,15), "grocery", "西日暮里スーパー",
              (35.7327, 139.7660), cost=3200,
              tp={"channel": "店舗", "brand": None}),
        _move(hm(11,15), hm(11,30), "walk", "walk", "→自宅",
              [(35.7327, 139.7660), home]),
        _stay(hm(11,30), hm(13), "lunch_home_w_kids", "自宅", home),
        _stay(hm(13), hm(15,30), "housework", "自宅", home),
        _move(hm(15,30), hm(15,55), "walk", "walk", "→霜降銀座 (子連れ)",
              [home, STN["nishi_nippori"], STN["tabata"], (35.7414, 139.7448)]),
        _stay(hm(15,55), hm(17), "shimofuri_stroll", "霜降銀座商店街",
              (35.7414, 139.7448),
              tp={"channel": "霜降銀座", "brand": None}),
        _stay(hm(17), hm(18,30), "shimofuri_dining",
              "Riverbed in Otherworld (家族)", rio, cost=4800,
              tp={"channel": "霜降銀座", "brand": "Riverbed in Otherworld"}),
        _move(hm(18,30), hm(19), "walk", "walk", "→自宅",
              [rio, STN["tabata"], STN["nishi_nippori"], home]),
        _stay(hm(19), hm(21,30), "family_time", "自宅", home),
        _stay(hm(21,30), hm(23), "leisure", "自宅", home),
        _stay(hm(23), 1440, "sleep", "自宅", home),
    ]


# 12. 井上 達也 (27 自動車部品工場 夜勤シフト)
def inoue(home: LatLng, weekend: bool, night_shift_today: bool) -> list[Segment]:
    factory = STN["kawaguchi_factory"]
    if night_shift_today:
        # 前夜22:00から夜勤、本日6:30まで勤務、その後睡眠
        return [
            _stay(0, hm(6,30), "night_shift", "自動車部品工場 (川口)",
                  factory, wage=11700),  # 6.5h * 1800
            _move(hm(6,30), hm(7,5), "car", "car", "→自宅",
                  [factory, home]),
            _stay(hm(7,5), hm(7,30), "breakfast_home", "自宅", home),
            _stay(hm(7,30), hm(15,30), "sleep", "自宅", home),  # 昼寝長め
            _stay(hm(15,30), hm(17), "leisure", "自宅", home,
                  tp={"channel": "YouTube", "brand": None}),
            _stay(hm(17), hm(18), "dinner_home", "自宅", home, cost=800),
            _stay(hm(18), hm(21), "leisure", "自宅", home,
                  tp={"channel": "YouTube", "brand": None}),
            # 夜勤再び — 出勤
            _move(hm(21), hm(21,35), "car", "car", "→工場 (夜勤)",
                  [home, factory]),
            _stay(hm(21,35), 1440, "night_shift",
                  "自動車部品工場 (川口)", factory, wage=4500),
        ]
    # 非夜勤の日
    return [
        _stay(0, hm(7), "sleep", "自宅", home),
        _stay(hm(7), hm(8,30), "morning_routine", "自宅", home),
        _stay(hm(8,30), hm(12), "leisure", "自宅", home),
        _stay(hm(12), hm(13), "lunch_home", "自宅", home),
        _stay(hm(13), hm(18), "leisure", "自宅", home),
        _stay(hm(18), hm(19), "dinner_home", "自宅", home, cost=1200),
        _stay(hm(19), hm(23), "leisure", "自宅", home),
        _stay(hm(23), 1440, "sleep", "自宅", home),
    ]


# ============================================================================
# Dispatcher
# ============================================================================

def schedule_for(persona_name: str, home: LatLng, target_date: date) -> list[Segment]:
    weekend = target_date.weekday() >= 5
    # シフト持ち（山本・井上）は本デモでは常に夜勤シフトとして表示する。
    # 実運用ではロスター（勤務表）から日次で引く。
    night_shift_today = True

    by_name = {
        "田中 浩二": lambda: tanaka(home, weekend),
        "山本 結衣": lambda: yamamoto(home, weekend, night_shift_today),
        "小林 章":   lambda: kobayashi(home, weekend),
        "鈴木 芽依": lambda: suzuki(home, weekend),
        "渡辺 健":   lambda: watanabe(home, weekend),
        "伊藤 桜":   lambda: ito(home, weekend),
        "中村 大輔": lambda: nakamura(home, weekend),
        "高橋 葵":   lambda: takahashi(home, weekend),
        "佐藤 美咲": lambda: sato(home, weekend),
        "林 涼":     lambda: hayashi(home, weekend),
        "森 花":     lambda: mori(home, weekend),
        "井上 達也": lambda: inoue(home, weekend, night_shift_today),
    }
    return by_name[persona_name]()
