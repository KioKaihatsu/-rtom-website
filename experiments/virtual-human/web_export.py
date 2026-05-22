"""Build real-time monitor payload from schedules and render HTML.

The HTML uses the visitor's clock (in Asia/Tokyo) to look up each persona's
currently active segment. Nothing past the current minute is rendered.
"""
from __future__ import annotations

import json
from datetime import date as date_t
from pathlib import Path
from typing import Any

from personas import build_cohort
from places import SHIMOFURI_GINZA, RIO, WORKPLACES, all_places
from schedules import Segment, schedule_for
from ec_events import generate_purchases


PALETTE = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#34495e", "#e67e22",
    "#d35400", "#8e44ad", "#16a085", "#c0392b",
]

MODE_LABEL = {
    "stay": "滞在中",
    "walk": "🚶 徒歩",
    "train": "🚃 電車",
    "bus":   "🚌 バス",
    "car":   "🚗 車",
}


def segment_to_dict(s: Segment) -> dict:
    return {
        "s": s.start_min,
        "e": s.end_min,
        "act": s.activity,
        "mode": s.mode,
        "place": s.place_name,
        "wp": [[round(p[0], 6), round(p[1], 6)] for p in s.waypoints],
        "cost": s.cost_jpy,
        "wage": s.wage_jpy,
        "tp": s.touchpoint,
    }


def build_payload(target_date: date_t) -> dict[str, Any]:
    cohort = build_cohort()
    personas_out = []
    for idx, persona in enumerate(cohort):
        t = persona.traits
        home = (t.home.lat, t.home.lng)
        segments = schedule_for(t.name, home, target_date)
        wp = WORKPLACES.get(t.workplace_id) if t.workplace_id else None
        personas_out.append({
            "id": idx + 1,
            "name": t.name,
            "color": PALETTE[idx % len(PALETTE)],
            "age": t.age,
            "gender": t.gender,
            "occupation": t.occupation,
            "income_jpy_year": t.income_jpy_year,
            "hourly_wage_jpy": t.hourly_wage_jpy,
            "home_name": t.home.name,
            "home_lat": t.home.lat,
            "home_lng": t.home.lng,
            "km_from_shimofuri": round(t.home.km_from_shimofuri(), 2),
            "workplace": (
                {"id": wp.id, "name": wp.name, "lat": wp.lat, "lng": wp.lng}
                if wp else None
            ),
            "initial_balance_jpy": persona.state.wallet_jpy,
            "segments": [segment_to_dict(s) for s in segments],
            "purchases": [
                p.to_dict()
                for p in generate_purchases(persona, [segment_to_dict(s) for s in segments], target_date)
            ],
        })

    return {
        "date": target_date.isoformat(),
        "weekday_jp": "月火水木金土日"[target_date.weekday()],
        "origin": {"lat": SHIMOFURI_GINZA.lat, "lng": SHIMOFURI_GINZA.lng},
        "rio": {"lat": RIO.lat, "lng": RIO.lng},
        "pois": [
            {"id": p.id, "name": p.name, "lat": p.lat,
             "lng": p.lng, "kind": p.kind}
            for p in all_places()
        ],
        "mode_label": MODE_LABEL,
        "personas": personas_out,
    }


def build_dual_payload() -> dict[str, Any]:
    """Build a payload with both weekday and weekend schedules embedded.

    Used by the iOS app so it can pick the correct schedule at runtime
    based on the visitor's current Tokyo day-of-week.
    """
    cohort = build_cohort()
    weekday_date = date_t(2026, 5, 18)  # Monday
    weekend_date = date_t(2026, 5, 17)  # Sunday

    personas_out = []
    for idx, persona in enumerate(cohort):
        t = persona.traits
        home = (t.home.lat, t.home.lng)
        wp = WORKPLACES.get(t.workplace_id) if t.workplace_id else None
        personas_out.append({
            "id": idx + 1,
            "name": t.name,
            "color": PALETTE[idx % len(PALETTE)],
            "age": t.age,
            "gender": t.gender,
            "occupation": t.occupation,
            "income_jpy_year": t.income_jpy_year,
            "hourly_wage_jpy": t.hourly_wage_jpy,
            "home_name": t.home.name,
            "home_lat": t.home.lat,
            "home_lng": t.home.lng,
            "km_from_shimofuri": round(t.home.km_from_shimofuri(), 2),
            "workplace": (
                {"id": wp.id, "name": wp.name, "lat": wp.lat, "lng": wp.lng}
                if wp else None
            ),
            "initial_balance_jpy": persona.state.wallet_jpy,
            "schedule_weekday": [
                segment_to_dict(s)
                for s in schedule_for(t.name, home, weekday_date)
            ],
            "schedule_weekend": [
                segment_to_dict(s)
                for s in schedule_for(t.name, home, weekend_date)
            ],
            "purchases_weekday": [
                p.to_dict() for p in generate_purchases(
                    persona,
                    [segment_to_dict(s) for s in schedule_for(t.name, home, weekday_date)],
                    weekday_date,
                )
            ],
            "purchases_weekend": [
                p.to_dict() for p in generate_purchases(
                    persona,
                    [segment_to_dict(s) for s in schedule_for(t.name, home, weekend_date)],
                    weekend_date,
                )
            ],
        })

    return {
        "origin": {"lat": SHIMOFURI_GINZA.lat, "lng": SHIMOFURI_GINZA.lng},
        "rio": {"lat": RIO.lat, "lng": RIO.lng},
        "pois": [
            {"id": p.id, "name": p.name, "lat": p.lat,
             "lng": p.lng, "kind": p.kind}
            for p in all_places()
        ],
        "mode_label": MODE_LABEL,
        "personas": personas_out,
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>霜降銀座コホート リアルタイム監視 — {date} ({weekday})</title>
<!-- PWA / iOS Add-to-Home-Screen -->
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="霜降銀座監視">
<meta name="theme-color" content="#0f1419">
<link rel="manifest" href="manifest.json">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  :root {{
    --bg:#0f1419; --panel:#1a1f2a; --line:#2a3142;
    --text:#e4e7eb; --dim:#8a93a3;
    --accent:#f6c350; --rio:#ffb84d;
    --green:#5dd39e; --red:#ef6f6c;
  }}
  *{{box-sizing:border-box}}
  html,body{{margin:0;height:100%;background:var(--bg);color:var(--text);
    font:13px/1.45 -apple-system,BlinkMacSystemFont,"Helvetica Neue","Hiragino Sans","Yu Gothic UI",sans-serif;
    -webkit-touch-callout:none;-webkit-user-select:none;overflow:hidden}}
  /* iPhone: stack the map and side panel */
  @media (max-width: 768px) {{
    #app{{grid-template-columns: 1fr !important; grid-template-rows: 1fr 56vh}}
    #map{{height: 100% !important}}
    #side{{border-left:0 !important; border-top:1px solid var(--line)}}
  }}
  /* iOS standalone (Add to Home Screen) safe areas */
  @supports (padding: env(safe-area-inset-top)) {{
    body{{padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}}
  }}
  #app{{display:grid;grid-template-columns:1fr 400px;height:100vh}}
  #map{{height:100%;background:#1f2530}}
  #side{{background:var(--panel);overflow-y:auto;border-left:1px solid var(--line)}}
  header{{padding:14px 16px;border-bottom:1px solid var(--line);
    position:sticky;top:0;background:var(--panel);z-index:5}}
  header h1{{margin:0 0 4px;font-size:14px;font-weight:700;letter-spacing:.04em}}
  header .clock{{font:700 22px ui-monospace,monospace;color:var(--accent);margin:6px 0}}
  header .sub{{color:var(--dim);font-size:11px}}
  header .scrub{{display:flex;align-items:center;gap:8px;margin-top:8px;font-size:11px;color:var(--dim)}}
  header .scrub input{{flex:1;accent-color:var(--accent)}}
  header button{{background:var(--accent);color:#1a1207;border:0;padding:3px 10px;
    border-radius:5px;font-weight:700;cursor:pointer;font-size:11px}}
  header button.live{{background:var(--green);color:#06281a}}
  .totals{{padding:12px 16px;border-bottom:1px solid var(--line);
    display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:11px}}
  .totals div b{{color:var(--accent);font:700 14px ui-monospace,monospace}}
  .totals span{{color:var(--dim);display:block;font-size:10px}}
  .person{{border-bottom:1px solid var(--line);padding:10px 14px;
    display:grid;grid-template-columns:14px 1fr;gap:10px;align-items:start}}
  .person .dot{{width:12px;height:12px;border-radius:50%;margin-top:4px;
    border:2px solid rgba(255,255,255,.2);position:relative}}
  .person .dot.moving::after{{content:'';position:absolute;inset:-4px;
    border-radius:50%;border:1.5px solid currentColor;opacity:.6;
    animation:pulse 1.4s ease-out infinite}}
  @keyframes pulse{{0%{{transform:scale(.7);opacity:.7}}100%{{transform:scale(1.6);opacity:0}}}}
  .person.sleeping{{opacity:.55}}
  .person .name{{font-weight:700;font-size:12px}}
  .person .age{{color:var(--dim);font-weight:400}}
  .person .occ{{color:var(--dim);font-size:10px;margin-bottom:4px}}
  .person .activity{{color:var(--accent);font-size:12px;font-weight:700;margin-bottom:2px}}
  .person .place{{color:var(--text);font-size:10px;margin-bottom:2px}}
  .person .mode{{color:var(--dim);font-size:10px;margin-bottom:4px}}
  .person.visiting-shotengai{{background:rgba(246,195,80,.08)}}
  .person.visiting-rio{{background:rgba(255,184,77,.18)}}
  .person.working{{border-left:3px solid var(--green);padding-left:11px}}
  .person.commuting{{border-left:3px solid #3498db;padding-left:11px}}
  .person .row{{display:flex;justify-content:space-between;
    font-size:11px;color:var(--dim);line-height:1.5}}
  .person .row b{{color:var(--text);font:600 11px ui-monospace,monospace}}
  .legend{{padding:10px 16px;border-bottom:1px solid var(--line);
    font-size:10px;color:var(--dim);line-height:1.5}}
  /* EC purchase feed */
  .feed{{padding:0 16px 8px;border-bottom:1px solid var(--line);
    max-height:260px;overflow:hidden;position:relative}}
  .feed h2{{font-size:11px;font-weight:700;color:var(--accent);
    margin:10px 0 6px;display:flex;justify-content:space-between;align-items:center}}
  .feed h2 .sum{{font:700 11px ui-monospace,monospace;color:var(--text)}}
  .feed-row{{display:grid;grid-template-columns:42px 1fr auto;gap:8px;
    padding:6px 0;border-bottom:1px dotted rgba(255,255,255,.05);
    font-size:11px}}
  .feed-row.new{{animation:slideIn .35s ease-out}}
  @keyframes slideIn{{from{{transform:translateX(-8px);opacity:0}}to{{transform:translateX(0);opacity:1}}}}
  .feed-row .time{{color:var(--dim);font:600 10px ui-monospace,monospace}}
  .feed-row .who{{color:var(--text);overflow:hidden}}
  .feed-row .who .sku{{font-size:10.5px;font-weight:600;color:var(--text);
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:block}}
  .feed-row .who .meta{{color:var(--dim);font-size:9.5px;display:block}}
  .feed-row .who .why{{color:var(--accent);font-size:9.5px;display:block;
    font-style:italic;opacity:.85}}
  .feed-row .price{{color:var(--accent);font:600 11.5px ui-monospace,monospace;
    text-align:right;white-space:nowrap}}
  .feed-row.impulse{{background:rgba(239,111,108,.08)}}
  /* Map purchase pulse */
  .buy-burst{{position:absolute;font-size:18px;pointer-events:none;
    animation:burst 1.2s ease-out forwards;color:var(--accent);
    text-shadow:0 0 6px rgba(0,0,0,.8);font-weight:700}}
  @keyframes burst{{
    0%{{transform:translate(-50%,-50%) scale(.5);opacity:0}}
    20%{{transform:translate(-50%,-110%) scale(1.2);opacity:1}}
    100%{{transform:translate(-50%,-180%) scale(.9);opacity:0}}
  }}
  /* Hourly histogram */
  .hist{{padding:10px 16px;border-bottom:1px solid var(--line)}}
  .hist h2{{font-size:11px;font-weight:700;color:var(--accent);margin:0 0 6px}}
  .hist svg{{width:100%;height:50px;display:block}}
  .hist .bar{{fill:var(--dim)}}
  .hist .bar.past{{fill:var(--accent)}}
  .hist .now{{stroke:var(--green);stroke-width:1.5;stroke-dasharray:2 2}}
  .hist .lbl{{fill:var(--dim);font:9px ui-monospace,monospace}}
</style>
</head>
<body>
<div id="app">
  <div id="map"></div>
  <aside id="side">
    <header>
      <h1>霜降銀座コホート 監視ステーション</h1>
      <div class="clock" id="clock">--:--:--</div>
      <div class="sub" id="dateLine">{date} ({weekday}) JST / N=12</div>
      <div class="sub" style="margin-top:4px">
        <a href="live-1000.html" style="color:var(--accent);text-decoration:none;font-weight:700">🗾 関東1000人ライブ</a>
        ·
        <a href="dashboard.html" style="color:var(--accent);text-decoration:none;font-weight:700">📊 N=1000 集計</a>
      </div>
      <div class="scrub">
        <span>過去を見る</span>
        <input type="range" id="scrub" min="0" max="1440" step="1" value="0"/>
        <button class="live" id="liveBtn">LIVE</button>
      </div>
    </header>
    <div class="totals" id="totals"></div>
    <div class="hist">
      <h2>EC 購買時間帯ヒストグラム</h2>
      <svg id="hist" viewBox="0 0 480 50" preserveAspectRatio="none"></svg>
    </div>
    <div class="feed">
      <h2>💸 直近のEC購買 <span class="sum" id="feedSum"></span></h2>
      <div id="feedRows"></div>
    </div>
    <div class="legend">
      ● 仮想人格12名の今この瞬間の位置・行動・収支・EC購買を可視化。
      位置は実線路（山手線/京浜東北/田園都市/三田/南北）と徒歩・電車・車。
      購買時には地図上に💸が舞う。<b style="color:var(--rio)">★</b> = RIO 来店中。
    </div>
    <div id="personList"></div>
  </aside>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = {payload_json};

const map = L.map('map', {{zoomControl: true, attributionControl: false}})
  .setView([DATA.origin.lat, DATA.origin.lng], 13);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  subdomains: 'abcd', maxZoom: 19,
  attribution: '© OpenStreetMap, © CARTO',
}}).addTo(map);

DATA.pois.forEach(p => {{
  const isRio = p.id === 'rio';
  const isShotengai = p.id === 'shimofuri_ginza';
  const color = isRio ? '#ffb84d' : isShotengai ? '#f6c350' : '#5e6b80';
  const radius = isRio ? 11 : isShotengai ? 13 : 5;
  L.circleMarker([p.lat, p.lng], {{
    radius, color, fillColor: color, fillOpacity: 0.35, weight: 2,
  }}).bindTooltip(p.name, {{direction: 'top'}}).addTo(map);
}});

L.circle([DATA.origin.lat, DATA.origin.lng], {{
  radius: 220, color: '#f6c350', fillOpacity: 0.04, weight: 1, dashArray: '4 4',
}}).addTo(map);

// Per-persona marker + trail
const personState = DATA.personas.map(p => {{
  const marker = L.circleMarker([p.home_lat, p.home_lng], {{
    radius: 7, color: '#ffffff', weight: 2,
    fillColor: p.color, fillOpacity: 0.95,
  }}).bindTooltip(p.name, {{direction: 'top'}}).addTo(map);
  const trail = L.polyline([], {{color: p.color, weight: 2,
                                opacity: 0.55, dashArray: '2 4'}}).addTo(map);
  return {{p, marker, trail}};
}});

// ----- Time helpers -----
function tokyoMinutes() {{
  const fmt = new Intl.DateTimeFormat('en-CA', {{
    timeZone: 'Asia/Tokyo',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  }});
  const parts = Object.fromEntries(
    fmt.formatToParts(new Date()).map(x => [x.type, x.value])
  );
  const m = parseInt(parts.hour) * 60 + parseInt(parts.minute)
          + parseInt(parts.second) / 60;
  return {{
    minutes: m,
    dateStr: `${{parts.year}}-${{parts.month}}-${{parts.day}}`,
    clock: `${{parts.hour}}:${{parts.minute}}:${{parts.second}} JST`,
  }};
}}

function findSegment(person, minutes) {{
  const segs = person.segments;
  // Linear search over ~15 segments is fine.
  for (let i = 0; i < segs.length; i++) {{
    if (minutes < segs[i].e) {{
      return minutes >= segs[i].s ? segs[i] : segs[Math.max(0, i - 1)];
    }}
  }}
  return segs[segs.length - 1];
}}

function positionInSegment(seg, minutes) {{
  if (seg.wp.length === 1) return seg.wp[0];
  const dur = Math.max(1, seg.e - seg.s);
  const frac = Math.max(0, Math.min(1, (minutes - seg.s) / dur));
  const n = seg.wp.length - 1;
  const idx = Math.min(Math.floor(frac * n), n - 1);
  const segF = frac * n - idx;
  const a = seg.wp[idx], b = seg.wp[idx + 1];
  return [a[0] + (b[0] - a[0]) * segF, a[1] + (b[1] - a[1]) * segF];
}}

function accumulated(person, minutes) {{
  let earned = 0, spent = 0;
  for (const s of person.segments) {{
    if (s.e <= minutes) {{
      earned += s.wage; spent += s.cost;
    }} else if (s.s <= minutes) {{
      const f = (minutes - s.s) / Math.max(1, s.e - s.s);
      earned += s.wage * f; spent += s.cost * f;
    }}
  }}
  return {{earned: Math.round(earned), spent: Math.round(spent)}};
}}

const ACT_LABEL = {{
  sleep: '💤 睡眠中',
  morning_routine: '🪥 朝の支度',
  morning_routine_w_baby: '🪥 朝の支度 (育児)',
  morning_routine_w_kids: '🪥 朝の支度 (子供と)',
  family_time: '👨‍👩‍👧 家族時間',
  childcare: '🍼 育児',
  housework: '🧺 家事',
  leisure: '🛋 くつろぎ',
  hobby: '🎨 趣味',
  errands: '📋 用事',
  errands_home: '📋 用事 (自宅)',
  shop_open: '🍶 開店準備',
  walk: '🚶 徒歩移動中',
  train: '🚃 電車移動中',
  bus: '🚌 バス移動中',
  car: '🚗 車移動中',
  work: '💻 勤務中',
  wfh_work: '🏠 在宅勤務中',
  night_shift: '🌙 夜勤勤務中',
  work_shop: '🍶 営業中 (居酒屋)',
  shop_prep: '🍶 仕込み',
  shop_cleanup: '🧽 後片付け',
  shopping_supply: '📦 仕入れ',
  class: '📚 授業',
  study_home: '📖 自習',
  study_night: '📖 夜の勉強',
  lunch_home: '🍱 ランチ (自宅)',
  lunch_konbini: '🍙 ランチ (コンビニ)',
  lunch_out: '🍱 外食ランチ',
  lunch_home_w_kids: '🍱 ランチ (子供と)',
  dinner_home: '🍳 夕食 (自宅)',
  dinner_out: '🍽 外食ディナー',
  breakfast_home: '🍞 朝食 (自宅)',
  grocery: '🛒 スーパー',
  shopping_apparel: '👕 アパレル',
  instagram_scroll: '📱 SNS',
  tv_time: '📺 TV鑑賞',
  wind_down: '🛀 リラックス',
  shimofuri_grocery: '🥬 霜降銀座で買物',
  shimofuri_dining: '⭐ Riverbed で食事',
  shimofuri_stroll: '🚶 商店街さんぽ',
}};

function fmtYen(n) {{ return (n||0).toLocaleString('ja-JP') + '円'; }}

// Build side panel
const list = document.getElementById('personList');
DATA.personas.forEach(p => {{
  const div = document.createElement('div');
  div.className = 'person';
  div.id = 'pp' + p.id;
  div.innerHTML = `
    <div class="dot" style="background:${{p.color}};color:${{p.color}}"></div>
    <div>
      <div class="name">${{p.name}} <span class="age">(${{p.age}})</span></div>
      <div class="occ">${{p.occupation}} / ${{p.home_name}} (${{p.km_from_shimofuri}}km)</div>
      <div class="activity" data-act></div>
      <div class="place" data-place></div>
      <div class="mode" data-mode></div>
      <div class="row"><span>残高</span><b data-balance>—</b></div>
      <div class="row"><span>本日収入</span><b data-earned>—</b></div>
      <div class="row"><span>本日支出</span><b data-spent>—</b></div>
    </div>`;
  list.appendChild(div);
}});

// Compute trail: positions sampled every 2 min over last 30 min.
function buildTrail(person, currentMin) {{
  const trail = [];
  for (let t = Math.max(0, currentMin - 30); t <= currentMin; t += 2) {{
    const seg = findSegment(person, t);
    trail.push(positionInSegment(seg, t));
  }}
  return trail;
}}

// Scrub state
const scrub = document.getElementById('scrub');
const liveBtn = document.getElementById('liveBtn');
let liveMode = true;

scrub.oninput = () => {{
  liveMode = false;
  liveBtn.style.background = 'var(--accent)';
  liveBtn.textContent = 'LIVE に戻る';
  update();
}};
liveBtn.onclick = () => {{
  liveMode = true;
  liveBtn.style.background = 'var(--green)';
  liveBtn.textContent = 'LIVE';
  update();
}};

// Track which purchases we've already shown a burst for
const burstSeen = new Set();

function escapeHtml(s) {{
  return String(s).replace(/[&<>"']/g, c => ({{
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }}[c]));
}}

function spawnBurst(latlng, price) {{
  const pt = map.latLngToContainerPoint(latlng);
  const mapEl = document.getElementById('map');
  const el = document.createElement('div');
  el.className = 'buy-burst';
  el.style.left = pt.x + 'px';
  el.style.top = pt.y + 'px';
  el.textContent = '💸 ¥' + price.toLocaleString('ja-JP');
  mapEl.appendChild(el);
  setTimeout(() => el.remove(), 1300);
}}

function update() {{
  const tk = tokyoMinutes();
  const liveMin = tk.minutes;
  // Scrubber max = current minute (no future allowed)
  scrub.max = Math.floor(liveMin);
  const minutes = liveMode ? liveMin : Math.min(+scrub.value, liveMin);
  if (liveMode) scrub.value = Math.floor(minutes);

  document.getElementById('clock').textContent = tk.clock + (liveMode ? '' : ' (履歴閲覧中)');
  document.getElementById('dateLine').textContent =
    `${{tk.dateStr}} (${{DATA.weekday_jp}}) JST / N=${{DATA.personas.length}}`;

  let totSleep = 0, totWork = 0, totShot = 0, totRio = 0;
  let totEarn = 0, totSpend = 0;
  let totECSpend = 0, totECCount = 0;

  personState.forEach(({{p, marker, trail}}) => {{
    const seg = findSegment(p, minutes);
    const pos = positionInSegment(seg, minutes);
    marker.setLatLng(pos);

    const moving = seg.mode !== 'stay';
    const tp = seg.tp;
    const atShot = tp && tp.channel === '霜降銀座';
    const atRio = tp && tp.brand === 'Riverbed in Otherworld';
    const sleeping = seg.act === 'sleep';
    const WORK_ACTS = new Set(['work', 'wfh_work', 'night_shift',
                                'work_shop', 'shop_prep', 'shop_cleanup']);
    const working = WORK_ACTS.has(seg.act);

    marker.setStyle({{
      radius: atRio ? 11 : atShot ? 9 : moving ? 8 : 7,
      color: atRio ? '#ffb84d' : sleeping ? '#888888' : '#ffffff',
      weight: atRio ? 3 : sleeping ? 1 : 2,
      fillOpacity: sleeping ? 0.6 : 0.95,
    }});

    // Trail
    trail.setLatLngs(buildTrail(p, minutes));

    if (sleeping) totSleep++;
    if (working) totWork++;
    if (atShot) totShot++;
    if (atRio) totRio++;

    const acc = accumulated(p, minutes);
    totEarn += acc.earned; totSpend += acc.spent;

    // EC purchases up to current minute
    let ecCount = 0, ecSpent = 0;
    (p.purchases || []).forEach(buy => {{
      if (buy.m <= minutes) {{
        ecCount++; ecSpent += buy.p;
        const key = `${{p.id}}-${{buy.m}}`;
        // Trigger burst animation if purchase just occurred (within last 4 sim minutes during live, OR within last 90 sec real-time of scrub)
        if (liveMode && (minutes - buy.m) <= 0.6 && !burstSeen.has(key)) {{
          spawnBurst(pos, buy.p);
          burstSeen.add(key);
        }}
      }}
    }});
    totECSpend += ecSpent;
    totECCount += ecCount;

    const el = document.getElementById('pp' + p.id);
    el.classList.toggle('sleeping', sleeping);
    el.classList.toggle('working', working);
    el.classList.toggle('commuting', moving);
    el.classList.toggle('visiting-shotengai', !!atShot && !atRio);
    el.classList.toggle('visiting-rio', !!atRio);
    el.querySelector('.dot').classList.toggle('moving', moving);

    el.querySelector('[data-act]').textContent =
      ACT_LABEL[seg.act] || seg.act;
    el.querySelector('[data-place]').textContent = '@ ' + seg.place;
    el.querySelector('[data-mode]').textContent =
      DATA.mode_label[seg.mode] + (moving
        ? `  (${{((minutes - seg.s) / Math.max(1, seg.e - seg.s) * 100).toFixed(0)}}% 到着まで)`
        : '');
    el.querySelector('[data-balance]').textContent =
      fmtYen(p.initial_balance_jpy + acc.earned - acc.spent);
    el.querySelector('[data-earned]').textContent = '+' + fmtYen(acc.earned);
    el.querySelector('[data-spent]').textContent = '−' + fmtYen(acc.spent);
  }});

  document.getElementById('totals').innerHTML = `
    <div><span>就寝中</span><b>${{totSleep}}人</b></div>
    <div><span>勤務中</span><b style="color:var(--green)">${{totWork}}人</b></div>
    <div><span>霜降銀座 滞在</span><b style="color:var(--accent)">${{totShot}}人</b></div>
    <div><span>RIO 来店</span><b style="color:var(--rio)">${{totRio}}人</b></div>
    <div><span>EC 累計購買</span><b>${{totECCount}}件 / ${{fmtYen(totECSpend)}}</b></div>
    <div><span>累計支出 (実店舗+EC)</span><b>${{fmtYen(totSpend + totECSpend)}}</b></div>`;

  // --- EC purchase feed (most recent 8 purchases up to now) ---
  // Use stable keys so DOM is only added/removed, not re-rendered (no flicker).
  const allBuys = [];
  DATA.personas.forEach(p => (p.purchases || []).forEach(b => {{
    if (b.m <= minutes) allBuys.push({{p, b}});
  }}));
  allBuys.sort((a, z) => z.b.m - a.b.m);  // newest first
  const visible = allBuys.slice(0, 8);
  const feedRows = document.getElementById('feedRows');

  const wantKeys = visible.map(({{p, b}}) => `${{p.id}}-${{b.m}}`);
  // Remove rows no longer in top-8
  Array.from(feedRows.children).forEach(child => {{
    if (!wantKeys.includes(child.dataset.key)) child.remove();
  }});
  // Add missing rows (in correct order) — new rows get animation
  visible.forEach(({{p, b}}, idx) => {{
    const key = `${{p.id}}-${{b.m}}`;
    let row = feedRows.querySelector(`[data-key="${{key}}"]`);
    if (!row) {{
      row = document.createElement('div');
      row.className = 'feed-row new' + (b.imp ? ' impulse' : '');
      row.dataset.key = key;
      const hh = String(Math.floor(b.m / 60)).padStart(2, '0');
      const mm = String(b.m % 60).padStart(2, '0');
      const tag = b.imp ? '💥' : '🛒';
      const lastName = (p.name.split(' ')[1] || p.name);
      const why = b.why || '';
      row.innerHTML = `
        <div class="time">${{hh}}:${{mm}}</div>
        <div class="who">
          <span class="sku">${{tag}} ${{escapeHtml(b.sku)}}</span>
          <span class="meta"><span style="color:${{p.color}}">●</span> ${{lastName}} · ${{b.ch}} · ${{b.cat}}</span>
          ${{why ? `<span class="why">${{escapeHtml(why)}}</span>` : ''}}
        </div>
        <div class="price">¥${{b.p.toLocaleString('ja-JP')}}</div>`;
      // Remove the animation class shortly so a future remount won't re-animate
      setTimeout(() => row.classList.remove('new'), 600);
    }}
    // Ensure row is at the correct index in the parent
    if (feedRows.children[idx] !== row) {{
      feedRows.insertBefore(row, feedRows.children[idx] || null);
    }}
  }});
  document.getElementById('feedSum').textContent =
    `${{allBuys.length}}件 ¥${{totECSpend.toLocaleString('ja-JP')}}`;

  // --- Hourly histogram (24 buckets) ---
  const buckets = new Array(24).fill(0);
  DATA.personas.forEach(p => (p.purchases || []).forEach(b => {{
    buckets[Math.floor(b.m / 60)]++;
  }}));
  const maxB = Math.max(1, ...buckets);
  const W = 480, H = 50, BW = W / 24, currentHour = minutes / 60;
  const bars = buckets.map((v, i) => {{
    const h = (v / maxB) * (H - 12);
    const isPast = i < currentHour;
    return `<rect class="bar ${{isPast ? 'past' : ''}}"
              x="${{i * BW + 1}}" y="${{H - h - 10}}"
              width="${{BW - 2}}" height="${{h}}"/>`;
  }}).join('');
  const labels = [0, 6, 12, 18, 23].map(h => {{
    return `<text class="lbl" x="${{h * BW + BW/2}}" y="${{H - 1}}" text-anchor="middle">${{h}}</text>`;
  }}).join('');
  const nowLine = `<line class="now" x1="${{currentHour * BW}}" y1="0"
                                       x2="${{currentHour * BW}}" y2="${{H - 10}}"/>`;
  document.getElementById('hist').innerHTML = bars + nowLine + labels;
}}

setInterval(update, 1000);
update();
</script>
</body>
</html>
"""


def render_html(payload: dict[str, Any], out_path: Path) -> None:
    html = HTML_TEMPLATE.format(
        date=payload["date"],
        weekday=payload["weekday_jp"],
        payload_json=json.dumps(payload, ensure_ascii=False),
    )
    out_path.write_text(html, encoding="utf-8")
