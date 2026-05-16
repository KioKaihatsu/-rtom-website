"""Render the simulation result as a self-contained HTML map monitor.

Output is a single .html file with Leaflet (loaded via CDN) and the
event time-series baked in. Opens directly in a browser.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from personas import build_cohort
from places import SHIMOFURI_GINZA, RIO, WORKPLACES, all_places
from simulator import simulate_day


PALETTE = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#34495e", "#e67e22",
    "#d35400", "#8e44ad", "#16a085", "#c0392b",
]


def build_payload(date_str: str) -> dict[str, Any]:
    start = datetime.strptime(date_str, "%Y-%m-%d")
    cohort = build_cohort()

    pois = []
    for p in all_places():
        pois.append({
            "id": p.id, "name": p.name, "lat": p.lat,
            "lng": p.lng, "kind": p.kind,
        })

    personas_out = []
    for idx, persona in enumerate(cohort):
        events = simulate_day(persona, start, seed=100 + idx)
        t = persona.traits
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
            "events": [
                {
                    "tick": e["tick"],
                    "lat": e["lat"],
                    "lng": e["lng"],
                    "action": e["action"],
                    "place_name": e["place_name"],
                    "place_kind": e["place_kind"],
                    "weather": e["world"]["weather"],
                    "temp_c": e["world"]["temperature_c"],
                    "cost": e["cost_jpy"],
                    "wage": e["wage_jpy"],
                    "balance": e["state"]["wallet_jpy"],
                    "earned_today": e["state"]["earned_today_jpy"],
                    "spent_today": e["state"]["spent_today_jpy"],
                    "distance_km": round(e["state"]["distance_km_today"], 2),
                    "touchpoint": e["touchpoint"],
                }
                for e in events
            ],
        })

    return {
        "date": date_str,
        "weekday_jp": "月火水木金土日"[start.weekday()],
        "origin": {"lat": SHIMOFURI_GINZA.lat, "lng": SHIMOFURI_GINZA.lng},
        "rio": {"lat": RIO.lat, "lng": RIO.lng},
        "pois": pois,
        "personas": personas_out,
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>霜降銀座コホート監視 — {date} ({weekday})</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  :root {{
    --bg: #0f1419;
    --panel: #1a1f2a;
    --line: #2a3142;
    --text: #e4e7eb;
    --dim: #8a93a3;
    --accent: #f6c350;
    --rio: #ffb84d;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; height: 100%;
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue",
                 "Hiragino Sans", "Yu Gothic UI", sans-serif;
    background: var(--bg); color: var(--text);
    font-size: 13px;
  }}
  #app {{ display: grid; grid-template-columns: 1fr 380px; height: 100vh; }}
  #map {{ height: 100%; background: #1f2530; }}
  #side {{
    background: var(--panel); overflow-y: auto;
    border-left: 1px solid var(--line); padding: 0;
  }}
  header {{
    padding: 14px 16px; border-bottom: 1px solid var(--line);
    position: sticky; top: 0; background: var(--panel); z-index: 5;
  }}
  header h1 {{
    margin: 0 0 4px; font-size: 14px; font-weight: 700;
    letter-spacing: 0.04em;
  }}
  header .sub {{ color: var(--dim); font-size: 11px; }}
  .controls {{
    position: absolute; left: 16px; bottom: 16px; right: 396px;
    background: rgba(15,20,25,0.88);
    border: 1px solid var(--line); border-radius: 10px;
    padding: 12px 16px; display: flex; align-items: center;
    gap: 12px; z-index: 1000; backdrop-filter: blur(8px);
  }}
  .controls button {{
    background: var(--accent); color: #1a1207; border: 0;
    padding: 6px 14px; border-radius: 6px; cursor: pointer;
    font-weight: 700; font-size: 12px;
  }}
  .controls button.secondary {{
    background: var(--panel); color: var(--text);
    border: 1px solid var(--line);
  }}
  .controls input[type=range] {{ flex: 1; accent-color: var(--accent); }}
  .controls .clock {{
    font-family: ui-monospace, monospace; font-size: 16px;
    min-width: 64px; color: var(--accent); font-weight: 700;
  }}
  .controls .weather {{ color: var(--dim); font-size: 11px; min-width: 110px; }}
  .person {{
    border-bottom: 1px solid var(--line); padding: 10px 16px;
    display: grid; grid-template-columns: 14px 1fr; gap: 10px;
    align-items: start;
  }}
  .person .dot {{
    width: 12px; height: 12px; border-radius: 50%;
    margin-top: 4px; border: 2px solid rgba(255,255,255,0.2);
  }}
  .person .name {{ font-weight: 700; font-size: 12px; }}
  .person .occ {{ color: var(--dim); font-size: 10px; margin-bottom: 4px; }}
  .person .row {{
    display: flex; justify-content: space-between;
    font-size: 11px; color: var(--dim); line-height: 1.5;
  }}
  .person .row b {{ color: var(--text); font-weight: 600; font-family: ui-monospace, monospace; }}
  .person .action {{
    color: var(--accent); font-size: 11px;
    font-weight: 600; margin-bottom: 3px;
  }}
  .person.visiting-shotengai {{ background: rgba(246, 195, 80, 0.08); }}
  .person.visiting-rio {{ background: rgba(255, 184, 77, 0.18); }}
  .person .place {{ color: var(--dim); font-size: 10px; margin-bottom: 4px; }}
  .legend {{
    padding: 10px 16px; border-bottom: 1px solid var(--line);
    font-size: 10px; color: var(--dim);
  }}
  .totals {{
    padding: 12px 16px; border-bottom: 1px solid var(--line);
    display: grid; grid-template-columns: 1fr 1fr; gap: 6px;
    font-size: 11px;
  }}
  .totals div b {{
    color: var(--accent); font-family: ui-monospace, monospace;
    font-weight: 700; font-size: 14px;
  }}
  .totals span {{ color: var(--dim); display: block; font-size: 10px; }}
</style>
</head>
<body>
<div id="app">
  <div id="map"></div>
  <aside id="side">
    <header>
      <h1>霜降銀座コホート監視 / {date} ({weekday})</h1>
      <div class="sub">N=12 仮想人格 / 半径15km / 24h リアルタイム再生</div>
    </header>
    <div class="totals" id="totals"></div>
    <div class="legend">
      ● 居住地から霜降銀座への距離・行動・収支を実時間で監視。
      <b style="color:var(--rio)">★</b> = Riverbed in Otherworld 来店中
    </div>
    <div id="personList"></div>
  </aside>
  <div class="controls">
    <button id="playBtn">▶</button>
    <div class="clock" id="clock">00:00</div>
    <input type="range" id="timeSlider" min="0" max="1440" step="5" value="0"/>
    <div class="weather" id="weather">—</div>
    <button class="secondary" id="speedBtn">1×</button>
  </div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = {payload_json};
const SPEEDS = [1, 2, 4, 8, 16, 32];
let speedIdx = 3; // 8x default = full day in 3 min

const map = L.map('map', {{
  zoomControl: false,
  attributionControl: false,
}}).setView([DATA.origin.lat, DATA.origin.lng], 13);

L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  subdomains: 'abcd',
  attribution: '© OpenStreetMap, © CARTO',
  maxZoom: 19,
}}).addTo(map);

// Plot fixed POIs (workplaces / Shimofuri Ginza / RIO)
DATA.pois.forEach(p => {{
  const color = p.id === 'rio' ? '#ffb84d'
              : p.id === 'shimofuri_ginza' ? '#f6c350'
              : '#5e6b80';
  const radius = p.id === 'rio' ? 12 : p.id === 'shimofuri_ginza' ? 14 : 6;
  L.circleMarker([p.lat, p.lng], {{
    radius, color, fillColor: color, fillOpacity: 0.35,
    weight: 2,
  }}).bindTooltip(p.name, {{permanent: false, direction: 'top'}}).addTo(map);
}});

// Highlight Shimofuri Ginza area
L.circle([DATA.origin.lat, DATA.origin.lng], {{
  radius: 200, color: '#f6c350', fillOpacity: 0.05, weight: 1,
  dashArray: '4 4',
}}).addTo(map);

// Per-persona marker + tracker
const personState = DATA.personas.map(p => {{
  const marker = L.circleMarker([p.home_lat, p.home_lng], {{
    radius: 7, color: '#ffffff', weight: 2,
    fillColor: p.color, fillOpacity: 0.95,
  }}).addTo(map);
  marker.bindTooltip(p.name, {{permanent: false, direction: 'top'}});
  return {{persona: p, marker, currentEvent: null}};
}});

// Build side-panel list
const list = document.getElementById('personList');
DATA.personas.forEach(p => {{
  const div = document.createElement('div');
  div.className = 'person';
  div.id = 'p' + p.id;
  div.innerHTML = `
    <div class="dot" style="background:${{p.color}}"></div>
    <div>
      <div class="name">${{p.name}} <span style="color:var(--dim);font-weight:400">(${{p.age}})</span></div>
      <div class="occ">${{p.occupation}} / ${{p.home_name}} (${{p.km_from_shimofuri}}km)</div>
      <div class="action" data-action></div>
      <div class="place" data-place></div>
      <div class="row"><span>残高</span><b data-balance>—</b></div>
      <div class="row"><span>本日収入</span><b data-earned>—</b></div>
      <div class="row"><span>本日支出</span><b data-spent>—</b></div>
      <div class="row"><span>移動距離</span><b data-distance>—</b></div>
    </div>`;
  list.appendChild(div);
}});

// Time helpers
function tickAt(minutes) {{
  const hour = Math.floor(minutes / 60);
  const frac = (minutes % 60) / 60;
  return {{hour: Math.min(23, hour), frac, isLastHour: hour >= 23}};
}}

function lerp(a, b, t) {{ return a + (b - a) * t; }}

function fmtYen(n) {{ return (n||0).toLocaleString('ja-JP') + '円'; }}

const ACTION_LABEL = {{
  sleep:'💤 睡眠', morning_routine:'🪥 朝の支度', commute:'🚃 通勤',
  work:'💻 勤務', wfh_work:'🏠 在宅勤務', lunch_out:'🍱 外食ランチ',
  lunch_konbini:'🍙 コンビニ', cafe_break:'☕ カフェ', coworker_chat:'💬 同僚と会話',
  shopping_apparel:'👕 アパレル', grocery:'🛒 スーパー', dinner_home:'🍳 家ディナー',
  dinner_out:'🍽 外食ディナー', netflix:'📺 Netflix', instagram_scroll:'📱 SNS',
  online_shopping:'📦 EC購入', workout:'🏃 運動', wind_down:'🛀 リラックス',
  shimofuri_grocery:'🥬 霜降銀座で買物', shimofuri_dining:'⭐ RIO で食事',
  shimofuri_stroll:'🚶 商店街さんぽ',
}};

function update(minutes) {{
  const {{hour, frac}} = tickAt(minutes);
  const nextHour = Math.min(23, hour + 1);
  document.getElementById('clock').textContent =
    String(hour).padStart(2,'0') + ':' + String(Math.floor(frac*60)).padStart(2,'0');

  let totShotengai = 0, totRio = 0, totSpend = 0, totEarn = 0;

  personState.forEach(({{persona, marker}}) => {{
    const cur = persona.events[hour];
    const nxt = persona.events[nextHour];
    const lat = lerp(cur.lat, nxt.lat, frac);
    const lng = lerp(cur.lng, nxt.lng, frac);
    marker.setLatLng([lat, lng]);

    const tp = cur.touchpoint;
    const atShotengai = tp && tp.channel === '霜降銀座';
    const atRio = tp && tp.brand === 'Riverbed in Otherworld';
    marker.setStyle({{
      radius: atRio ? 11 : atShotengai ? 9 : 7,
      color: atRio ? '#ffb84d' : '#ffffff',
      weight: atRio ? 3 : 2,
    }});

    const el = document.getElementById('p' + persona.id);
    el.classList.toggle('visiting-shotengai', !!atShotengai && !atRio);
    el.classList.toggle('visiting-rio', !!atRio);
    el.querySelector('[data-action]').textContent =
      ACTION_LABEL[cur.action] || cur.action;
    el.querySelector('[data-place]').textContent =
      '@ ' + cur.place_name;
    el.querySelector('[data-balance]').textContent = fmtYen(cur.balance);
    el.querySelector('[data-earned]').textContent = '+' + fmtYen(cur.earned_today);
    el.querySelector('[data-spent]').textContent = '−' + fmtYen(cur.spent_today);
    el.querySelector('[data-distance]').textContent = cur.distance_km.toFixed(2) + ' km';

    if (atShotengai) totShotengai++;
    if (atRio) totRio++;
    totSpend += cur.spent_today;
    totEarn += cur.earned_today;
  }});

  const w = DATA.personas[0].events[hour];
  document.getElementById('weather').textContent =
    `${{w.weather}} / ${{w.temp_c.toFixed(1)}}℃`;
  document.getElementById('totals').innerHTML = `
    <div><span>霜降銀座 現在訪問</span><b>${{totShotengai}}人</b></div>
    <div><span>RIO 現在来店</span><b style="color:var(--rio)">${{totRio}}人</b></div>
    <div><span>本日 累計収入</span><b>${{fmtYen(totEarn)}}</b></div>
    <div><span>本日 累計支出</span><b>${{fmtYen(totSpend)}}</b></div>`;
}}

// Playback
const slider = document.getElementById('timeSlider');
slider.oninput = () => {{ update(+slider.value); }};

let playing = false, lastTs = 0;
const playBtn = document.getElementById('playBtn');
playBtn.onclick = () => {{ playing = !playing; playBtn.textContent = playing ? '⏸' : '▶'; }};

const speedBtn = document.getElementById('speedBtn');
speedBtn.onclick = () => {{
  speedIdx = (speedIdx + 1) % SPEEDS.length;
  speedBtn.textContent = SPEEDS[speedIdx] + '×';
}};
speedBtn.textContent = SPEEDS[speedIdx] + '×';

function frame(ts) {{
  if (playing) {{
    const dt = (ts - lastTs) / 1000;
    // 1 real second = SPEEDS[idx] simulated minutes
    let v = +slider.value + dt * SPEEDS[speedIdx];
    if (v > 1440) {{ v = 1440; playing = false; playBtn.textContent = '▶'; }}
    slider.value = v;
    update(v);
  }}
  lastTs = ts;
  requestAnimationFrame(frame);
}}
requestAnimationFrame(frame);
update(0);
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
