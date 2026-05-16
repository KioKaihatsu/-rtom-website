"""Monitoring CLI / HTML map exporter for the 12-persona cohort.

Usage:
    python3 monitor.py                              # CLI + HTML
    python3 monitor.py --no-anim                    # CLI without per-tick animation
    python3 monitor.py --date 2026-05-18            # simulate a Monday
    python3 monitor.py --no-cli                     # only emit HTML
    python3 monitor.py --html out/monitor.html      # custom HTML output path
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
from simulator import simulate_day
from web_export import build_payload, render_html


CSI = "\033["
CLEAR = f"{CSI}2J{CSI}H"
DIM = f"{CSI}2m"
BOLD = f"{CSI}1m"
RESET = f"{CSI}0m"
YELLOW = f"{CSI}33m"
CYAN = f"{CSI}36m"


def cli_dashboard(payload: dict, animate: bool) -> None:
    weekday = payload["weekday_jp"]
    personas = payload["personas"]
    header = (
        f"{BOLD}=== 霜降銀座コホート監視 / {payload['date']} ({weekday}) "
        f"/ N={len(personas)} ==={RESET}"
    )

    for hour in range(24):
        if animate:
            sys.stdout.write(CLEAR)
        print(header)
        ev0 = personas[0]["events"][hour]
        print(f"{DIM}{hour:02d}:00  天気 {ev0['weather']}  "
              f"気温 {ev0['temp_c']}℃{RESET}\n")
        print(f"{'#':<3}{'氏名':<10}{'場所':<22}{'行動':<22}"
              f"{'残高':<11}{'本日収入':<10}{'移動'}")
        print("-" * 96)
        for i, p in enumerate(personas, 1):
            e = p["events"][hour]
            tp = e["touchpoint"]
            highlight = ""
            if tp and tp.get("brand") == "Riverbed in Otherworld":
                highlight = YELLOW
            elif tp and tp["channel"] == "霜降銀座":
                highlight = CYAN
            row = (
                f"{i:<3}"
                f"{p['name']:<9} "
                f"{e['place_name'][:20]:<22}"
                f"{e['action']:<22}"
                f"{e['balance']:>7,}円  "
                f"{e['earned_today']:>6,}円 "
                f"{e['distance_km']:>4.1f}km"
            )
            print(f"{highlight}{row}{RESET}")
        if animate:
            time.sleep(0.16)

    # ----- Final dashboard -----
    print("\n" + BOLD + "=" * 96 + RESET)
    print(f"{BOLD}📊 24時間サマリー{RESET}\n")

    channel_counts = Counter()
    brand_counts = Counter()
    rio_visits = []
    shimofuri_log = []
    hour_heat = defaultdict(int)

    summary = []
    for p in personas:
        final = p["events"][-1]
        summary.append({
            "name": p["name"],
            "balance": final["balance"],
            "earned": final["earned_today"],
            "spent": final["spent_today"],
            "distance": final["distance_km"],
        })
        for e in p["events"]:
            tp = e["touchpoint"]
            if tp:
                channel_counts[tp["channel"]] += 1
                if tp["brand"]:
                    brand_counts[tp["brand"]] += 1
                if tp["channel"] == "霜降銀座":
                    hour_heat[e["tick"]] += 1
                    shimofuri_log.append((p["name"], e["tick"], e["action"]))
                    if tp.get("brand") == "Riverbed in Otherworld":
                        rio_visits.append((p["name"], e["tick"]))

    print(f"{BOLD}収支サマリー（収入 - 支出 = ネット）{RESET}")
    print(f"  {'氏名':<10} {'残高':>9}  {'収入':>9}  {'支出':>9}  {'移動':>7}")
    for s in sorted(summary, key=lambda x: -x["earned"]):
        print(f"  {s['name']:<10} {s['balance']:>7,}円  "
              f"+{s['earned']:>7,}円  −{s['spent']:>7,}円  "
              f"{s['distance']:>5.1f}km")

    print(f"\n{BOLD}チャネル別接触{RESET}")
    for ch, n in channel_counts.most_common():
        bar = "█" * min(n, 40)
        color = YELLOW if ch == "霜降銀座" else ""
        print(f"  {color}{ch:<14}{RESET} {n:>3}  {color}{bar}{RESET}")

    print(f"\n{BOLD}⭐ RIO 来店候補{RESET}")
    if rio_visits:
        for name, h in rio_visits:
            print(f"  {YELLOW}{h:02d}:00  {name}{RESET}")
    else:
        print(f"  {DIM}(本日来店なし){RESET}")

    print(f"\n{BOLD}🥬 霜降銀座への来訪{RESET}")
    for name, h, act in shimofuri_log:
        color = YELLOW if act == "shimofuri_dining" else CYAN
        print(f"  {color}{h:02d}:00  {name:<10}  "
              f"{act.replace('shimofuri_', '')}{RESET}")

    print(f"\n{BOLD}時間帯ヒートマップ（霜降銀座総接触）{RESET}")
    if hour_heat:
        peak = max(hour_heat.values())
        for h in range(24):
            n = hour_heat.get(h, 0)
            bar = "█" * n
            if n == peak and n > 0:
                bar = f"{YELLOW}{bar}{RESET}"
            print(f"  {h:02d} │ {bar}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-05-16",
                    help="シミュレーション対象日 (YYYY-MM-DD)")
    ap.add_argument("--no-anim", action="store_true",
                    help="CLI のアニメーション無効")
    ap.add_argument("--no-cli", action="store_true",
                    help="CLI ダッシュボード省略 (HTML のみ生成)")
    ap.add_argument("--html", type=Path,
                    default=Path("out/monitor.html"),
                    help="HTML 出力パス")
    ap.add_argument("--json", type=Path, default=None,
                    help="生データ JSON 出力パス")
    args = ap.parse_args()

    payload = build_payload(args.date)

    if not args.no_cli:
        cli_dashboard(payload, animate=not args.no_anim)

    args.html.parent.mkdir(parents=True, exist_ok=True)
    render_html(payload, args.html)
    print(f"\n{DIM}🗺  HTML monitor: {args.html}{RESET}")
    print(f"{DIM}    open: file://{args.html.resolve()}{RESET}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"{DIM}    JSON: {args.json}{RESET}")


if __name__ == "__main__":
    main()
