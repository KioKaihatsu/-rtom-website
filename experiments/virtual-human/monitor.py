"""Real-time monitor: prints the cohort's CURRENT state (Asia/Tokyo) and
emits the HTML monitor for live browser viewing.

No future events are projected. The schedule is just a lookup table.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from web_export import build_payload, render_html, MODE_LABEL


CSI = "\033["
DIM = f"{CSI}2m"
BOLD = f"{CSI}1m"
RESET = f"{CSI}0m"
YELLOW = f"{CSI}33m"
GREEN = f"{CSI}32m"
CYAN = f"{CSI}36m"
GREY = f"{CSI}90m"
BLUE = f"{CSI}34m"


def find_segment(segments: list[dict], minute: float) -> dict:
    for i, s in enumerate(segments):
        if minute < s["e"]:
            return s if minute >= s["s"] else segments[max(0, i - 1)]
    return segments[-1]


def accumulated(segments: list[dict], minute: float) -> tuple[int, int]:
    earned = spent = 0.0
    for s in segments:
        if s["e"] <= minute:
            earned += s["wage"]
            spent += s["cost"]
        elif s["s"] <= minute:
            f = (minute - s["s"]) / max(1, s["e"] - s["s"])
            earned += s["wage"] * f
            spent += s["cost"] * f
    return round(earned), round(spent)


def print_now(payload: dict, now_jst: datetime) -> None:
    minute = now_jst.hour * 60 + now_jst.minute + now_jst.second / 60.0
    weekday = "月火水木金土日"[now_jst.weekday()]
    print(f"{BOLD}━━━ 霜降銀座コホート 監視ステーション ━━━{RESET}")
    print(f"{GREY}現在 (JST): {now_jst.strftime('%Y-%m-%d %H:%M:%S')} ({weekday}){RESET}")
    print(f"{GREY}N=12  /  origin: 霜降銀座商店街{RESET}")
    print()

    print(f"{'#':<3}{'氏名':<10}{'今やっていること':<28}{'場所/モード':<26}{'本日収支':>14}")
    print("─" * 82)

    sleeping = working = at_shot = at_rio = 0
    sum_earn = sum_spend = 0

    for idx, p in enumerate(payload["personas"], 1):
        seg = find_segment(p["segments"], minute)
        earned, spent = accumulated(p["segments"], minute)
        balance = p["initial_balance_jpy"] + earned - spent
        sum_earn += earned
        sum_spend += spent

        act = seg["act"]
        mode = seg["mode"]
        tp = seg["tp"]

        WORK_ACTS = {
            "work", "wfh_work", "night_shift",
            "work_shop", "shop_prep", "shop_cleanup",
        }
        if act == "sleep":
            sleeping += 1
            colour = GREY
        elif act == "night_shift":
            working += 1
            colour = BLUE
        elif act in WORK_ACTS:
            working += 1
            colour = GREEN
        elif tp and tp.get("brand") == "Riverbed in Otherworld":
            at_rio += 1; at_shot += 1
            colour = YELLOW
        elif tp and tp["channel"] == "霜降銀座":
            at_shot += 1
            colour = CYAN
        elif mode != "stay":
            colour = BLUE
        else:
            colour = ""

        mode_lab = MODE_LABEL[mode]
        if mode != "stay":
            f = (minute - seg["s"]) / max(1, seg["e"] - seg["s"])
            mode_lab += f" ({f*100:.0f}%)"

        line = (
            f"{idx:<3}{p['name']:<9} "
            f"{act:<28}"
            f"{seg['place']!s:<14} {mode_lab:<12}"
            f"  {balance:>7,}円"
        )
        print(f"{colour}{line}{RESET}")

    print()
    print(f"{BOLD}コホート状況{RESET}")
    print(f"  {GREY}就寝中{RESET}     {sleeping}人")
    print(f"  {GREEN}勤務中{RESET}     {working}人")
    print(f"  {CYAN}霜降銀座滞在{RESET}  {at_shot}人")
    print(f"  {YELLOW}RIO 来店{RESET}     {at_rio}人")
    print(f"  累計収入   +{sum_earn:,}円")
    print(f"  累計支出   −{sum_spend:,}円")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None,
                    help="観測日 (YYYY-MM-DD, JST). 省略時は今日.")
    ap.add_argument("--html", type=Path,
                    default=Path("out/monitor.html"),
                    help="HTML 出力パス")
    ap.add_argument("--no-html", action="store_true",
                    help="HTML 生成をスキップ")
    ap.add_argument("--no-cli", action="store_true",
                    help="CLI 出力をスキップ")
    ap.add_argument("--at", default=None,
                    help="表示時刻を指定 (HH:MM) — デバッグ用")
    args = ap.parse_args()

    jst = ZoneInfo("Asia/Tokyo")
    now_jst = datetime.now(jst)
    if args.date:
        d = datetime.strptime(args.date, "%Y-%m-%d").date()
        now_jst = now_jst.replace(year=d.year, month=d.month, day=d.day)
    if args.at:
        h, m = map(int, args.at.split(":"))
        now_jst = now_jst.replace(hour=h, minute=m, second=0)

    payload = build_payload(now_jst.date())

    if not args.no_cli:
        print_now(payload, now_jst)

    if not args.no_html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        render_html(payload, args.html)
        print(f"\n{DIM}🗺  HTML monitor: {args.html}{RESET}")
        print(f"{DIM}    open: file://{args.html.resolve()}{RESET}")


if __name__ == "__main__":
    main()
