"""Monitoring CLI for the 12-persona cohort.

Usage:
    python3 monitor.py                # animated tick-by-tick view + final report
    python3 monitor.py --no-anim      # skip animation
    python3 monitor.py --date 2026-05-18  # simulate a Monday
    python3 monitor.py --json out/   # also write JSON artefacts

The tool runs all 12 personas through a 24-hour day, prints an SRE-style
snapshot of what everyone is doing each tick, and finishes with a
marketing dashboard focused on 霜降銀座 / Riverbed in Otherworld touch.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from personas import build_cohort
from simulator import ACTIONS, simulate_day


# ANSI helpers
CSI = "\033["
CLEAR = f"{CSI}2J{CSI}H"
DIM = f"{CSI}2m"
BOLD = f"{CSI}1m"
RESET = f"{CSI}0m"
YELLOW = f"{CSI}33m"
GREEN = f"{CSI}32m"
CYAN = f"{CSI}36m"
RED = f"{CSI}31m"
MAGENTA = f"{CSI}35m"


ACTION_SYMBOLS = {
    "sleep": "💤", "morning_routine": "🪥", "commute": "🚃",
    "work": "💻", "wfh_work": "🏠", "lunch_out": "🍱",
    "lunch_konbini": "🍙", "cafe_break": "☕", "coworker_chat": "💬",
    "shopping_apparel": "👕", "grocery": "🛒", "dinner_home": "🍳",
    "dinner_out": "🍽️ ", "netflix": "📺", "instagram_scroll": "📱",
    "online_shopping": "📦", "workout": "🏃", "wind_down": "🛀",
    "shimofuri_grocery": "🥬", "shimofuri_dining": "⭐",
    "shimofuri_stroll": "🚶",
}


def fmt_action(action: str) -> str:
    sym = ACTION_SYMBOLS.get(action, "·")
    label = action.replace("shimofuri_", "霜降")
    return f"{sym} {label:<14}"


def run(date_str: str, animate: bool, json_dir: Path | None) -> None:
    start = datetime.strptime(date_str, "%Y-%m-%d")
    cohort = build_cohort()
    all_events: dict[str, list[dict]] = {}

    # Simulate every persona with a stable per-person seed.
    for idx, p in enumerate(cohort):
        all_events[p.traits.name] = simulate_day(p, start, seed=100 + idx)

    weekday_jp = "月火水木金土日"[start.weekday()]
    header = (
        f"{BOLD}=== 霜降銀座コホート監視 / {start.date()} ({weekday_jp}) "
        f"/ N={len(cohort)} ==={RESET}"
    )

    # --- Animated per-hour snapshots ---
    for hour in range(24):
        if animate:
            sys.stdout.write(CLEAR)
        print(header)
        # World context is identical for all (we shared a Tokyo region).
        w = all_events[cohort[0].traits.name][hour]["world"]
        print(
            f"{DIM}{w['datetime'][11:16]}  天気 {w['weather']}  "
            f"気温 {w['temperature_c']}℃  湿度 {int(w['humidity']*100)}%"
            f"{RESET}"
        )
        print()
        print(f"{'#':<3}{'氏名':<10}{'居住地':<18}{'距離':<8}"
              f"{'行動':<22}{'状態':<14}{'支出'}")
        print("-" * 88)
        for i, p in enumerate(cohort, 1):
            ev = all_events[p.traits.name][hour]
            t = p.traits
            km = t.home.km_from_shimofuri()
            action = ev["action"]
            row = (
                f"{i:<3}"
                f"{t.name:<10}"
                f"{t.home.name:<17} "
                f"{km:>4.1f}km "
                f"{fmt_action(action):<22}"
                f"E{int(ev['state']['energy']*9)}"
                f" H{int(ev['state']['hunger']*9)}"
                f" S{int(ev['state']['stress']*9)}  "
                f"{ev['cost_jpy']:>5}円"
            )
            tp = ev["touchpoint"]
            if tp and tp["channel"] == "霜降銀座":
                accent = YELLOW if tp.get("brand") == "Riverbed in Otherworld" else CYAN
                row = f"{accent}{row}{RESET}"
                if tp.get("brand"):
                    row += f"  {accent}★ {tp['brand']}{RESET}"
            print(row)

        if animate:
            time.sleep(0.18)

    # --- Final marketing dashboard ---
    print()
    print(f"{BOLD}{'='*88}{RESET}")
    print(f"{BOLD}📊 マーケティング集計（24時間）{RESET}")
    print(f"{BOLD}{'='*88}{RESET}")

    # Aggregate channel exposure
    channel_counts: Counter[str] = Counter()
    brand_counts: Counter[str] = Counter()
    spend_by_persona: dict[str, int] = {}
    shimofuri_visits: list[tuple[str, int, str]] = []
    rio_visitors: list[tuple[str, int]] = []
    hour_heatmap: dict[int, int] = defaultdict(int)

    for name, events in all_events.items():
        spend = sum(e["cost_jpy"] for e in events)
        spend_by_persona[name] = spend
        for e in events:
            tp = e["touchpoint"]
            if not tp:
                continue
            channel_counts[tp["channel"]] += 1
            if tp["brand"]:
                brand_counts[tp["brand"]] += 1
            if tp["channel"] == "霜降銀座":
                hour_heatmap[e["world"]["hour"]] += 1
                shimofuri_visits.append((name, e["world"]["hour"], e["action"]))
                if tp.get("brand") == "Riverbed in Otherworld":
                    rio_visitors.append((name, e["world"]["hour"]))

    print(f"\n{BOLD}チャネル別接触数{RESET}")
    for ch, n in channel_counts.most_common():
        bar = "█" * min(n, 40)
        color = YELLOW if ch == "霜降銀座" else ""
        print(f"  {color}{ch:<14}{RESET} {n:>3}  {color}{bar}{RESET}")

    print(f"\n{BOLD}ブランド露出{RESET}")
    for b, n in brand_counts.most_common():
        color = YELLOW if b == "Riverbed in Otherworld" else ""
        print(f"  {color}{b:<26}{RESET} {n}")

    print(f"\n{BOLD}🥬 霜降銀座への来訪（人 × 時間 × 行動）{RESET}")
    if shimofuri_visits:
        for name, h, act in shimofuri_visits:
            color = YELLOW if act == "shimofuri_dining" else CYAN
            print(f"  {color}{h:02d}:00  {name:<10}  {act.replace('shimofuri_', '')}{RESET}")
    else:
        print(f"  {DIM}(なし){RESET}")

    print(f"\n{BOLD}⭐ Riverbed in Otherworld 来店候補{RESET}")
    if rio_visitors:
        for name, h in rio_visitors:
            print(f"  {YELLOW}{h:02d}:00  {name}{RESET}")
    else:
        print(f"  {DIM}(本日来店なし — 雨天や立地遠の影響を確認){RESET}")

    print(f"\n{BOLD}時間帯ヒートマップ（霜降銀座総接触）{RESET}")
    if hour_heatmap:
        peak = max(hour_heatmap.values())
        for h in range(24):
            n = hour_heatmap.get(h, 0)
            bar = "█" * n
            if n == peak and n > 0:
                bar = f"{YELLOW}{bar}{RESET}"
            print(f"  {h:02d} │ {bar}")
    else:
        print(f"  {DIM}(接触なし){RESET}")

    print(f"\n{BOLD}支出ランキング{RESET}")
    for name, spend in sorted(spend_by_persona.items(),
                              key=lambda x: -x[1])[:5]:
        print(f"  {spend:>6,}円  {name}")

    # Distance vs Shimofuri visits correlation summary
    print(f"\n{BOLD}距離 × 来訪{RESET}")
    by_distance = sorted(cohort, key=lambda p: p.traits.home.km_from_shimofuri())
    for p in by_distance:
        visits = sum(
            1 for e in all_events[p.traits.name]
            if e["touchpoint"] and e["touchpoint"]["channel"] == "霜降銀座"
        )
        bar = "●" * visits if visits else f"{DIM}·{RESET}"
        km = p.traits.home.km_from_shimofuri()
        print(f"  {km:>5.1f}km  {p.traits.name:<10}  {bar}")

    # JSON artefact dump
    if json_dir:
        json_dir.mkdir(parents=True, exist_ok=True)
        (json_dir / "cohort.json").write_text(
            json.dumps(
                [p.snapshot() for p in cohort], ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
        (json_dir / "events.json").write_text(
            json.dumps(all_events, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report = {
            "date": start.date().isoformat(),
            "n_personas": len(cohort),
            "channel_counts": dict(channel_counts),
            "brand_counts": dict(brand_counts),
            "shimofuri_visits": [
                {"name": n, "hour": h, "action": a}
                for n, h, a in shimofuri_visits
            ],
            "rio_visitors": [{"name": n, "hour": h} for n, h in rio_visitors],
            "hour_heatmap": dict(hour_heatmap),
            "spend_by_persona": spend_by_persona,
        }
        (json_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n{DIM}JSON 書き出し: {json_dir}/{RESET}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-05-16",
                    help="シミュレーション対象日 (YYYY-MM-DD)")
    ap.add_argument("--no-anim", action="store_true",
                    help="毎時のクリア/ウェイトを省略")
    ap.add_argument("--json", type=Path, default=None,
                    help="JSON 出力ディレクトリ")
    args = ap.parse_args()
    run(args.date, animate=not args.no_anim, json_dir=args.json)


if __name__ == "__main__":
    main()
