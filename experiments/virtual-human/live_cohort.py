"""関東圏 1000人リアルタイム監視 HTML 生成。

地図上に N=1000 のドットを Canvas レンダリングでプロットし、
Asia/Tokyo 時刻に同期して移動・購買バーストを表示する。
"""
from __future__ import annotations

import argparse
import json
from datetime import date as date_t, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from cohort_generator import generate_cohort, schedule_template
from ec_events import generate_purchases, personality_blurb, derive_interests


# Color by template (visible at small dot size)
TEMPLATE_COLOR = {
    "office":     "#3498db",   # blue
    "wfh":        "#9b59b6",   # purple
    "student":    "#f39c12",   # orange
    "retired":    "#7f8c8d",   # gray
    "home":       "#e91e63",   # pink
    "shift":      "#f1c40f",   # yellow
    "healthcare": "#2ecc71",   # green
    "retail":     "#e67e22",   # dark orange
}

ACT_GROUP = {
    "sleep":               "sleep",
    "morning_routine":     "home",
    "morning_routine_w_baby": "home",
    "morning_routine_w_kids": "home",
    "breakfast_home":      "home",
    "lunch_home":          "home",
    "lunch_home_w_kids":   "home",
    "dinner_home":         "home",
    "family_time":         "home",
    "leisure":             "leisure",
    "tv_time":             "leisure",
    "wind_down":           "leisure",
    "instagram_scroll":    "leisure",
    "hobby":               "leisure",
    "study_home":          "study",
    "errands":             "out",
    "housework":           "home",
    "childcare":           "home",
    "train":               "commute",
    "work":                "work",
    "wfh_work":            "work",
}


def build(n: int, target_date: date_t, seed: int = 42) -> dict[str, Any]:
    cohort = generate_cohort(n, seed=seed)
    weekend = target_date.weekday() >= 5

    personas_out = []
    purchases_out = []
    for p in cohort:
        t = p.traits
        segs_dicts = schedule_template(t.template, weekend)
        buys = generate_purchases(p, segs_dicts, target_date)
        # Compress segments
        seg_min = [{
            "s": s["s"], "e": s["e"], "a": s["act"], "m": s["mode"],
        } for s in segs_dicts]
        # Top 3 brand affinities for display
        top_brands = sorted(t.brand_affinity.items(),
                            key=lambda x: -x[1])[:3]
        personas_out.append({
            "i": len(personas_out),
            "n": t.name,
            "a": t.age,
            "g": "M" if t.gender == "male" else "F",
            "o": t.occupation,
            "tpl": t.template,
            "inc": t.income_jpy_year,
            "pref": t.prefecture,
            "h": [t.home_lat, t.home_lng],
            "w": ([t.commute_target_lat, t.commute_target_lng]
                  if t.commute_target_lat is not None else None),
            "c": TEMPLATE_COLOR.get(t.template, "#888"),
            "seg": seg_min,
            # Rich insight fields
            "blurb": personality_blurb(p),
            "interests": derive_interests(p),
            "brands": [{"name": b, "score": round(s, 2)} for b, s in top_brands],
        })
        for b in buys:
            purchases_out.append({
                "pid": personas_out[-1]["i"],
                "n":   t.name,
                "m":   b.minute,
                "ch":  b.channel,
                "cat": b.category,
                "sku": b.sku,
                "p":   b.price_jpy,
                "imp": b.impulse,
                "why": b.reason,
                "whys": list(b.why_lines),
                "act": b.trigger_action,
                "lat": t.home_lat,
                "lng": t.home_lng,
            })
    purchases_out.sort(key=lambda x: x["m"])

    return {
        "date": target_date.isoformat(),
        "weekday_jp": "月火水木金土日"[target_date.weekday()],
        "n_personas": n,
        "n_purchases": len(purchases_out),
        "total_spend": sum(b["p"] for b in purchases_out),
        "personas": personas_out,
        "purchases": purchases_out,
        "generated_at": datetime.now(ZoneInfo("Asia/Tokyo"))
                                 .strftime("%Y-%m-%d %H:%M:%S JST"),
        "template_legend": [
            ("office",     "会社員・公務員・教員", TEMPLATE_COLOR["office"]),
            ("wfh",        "リモートワーカー",      TEMPLATE_COLOR["wfh"]),
            ("healthcare", "看護師",                TEMPLATE_COLOR["healthcare"]),
            ("shift",      "シフト勤務",            TEMPLATE_COLOR["shift"]),
            ("retail",     "販売員",                TEMPLATE_COLOR["retail"]),
            ("student",    "学生",                  TEMPLATE_COLOR["student"]),
            ("home",       "主婦・主夫",            TEMPLATE_COLOR["home"]),
            ("retired",    "退職",                  TEMPLATE_COLOR["retired"]),
        ],
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>関東 N={n_personas}人 ライブ EC 監視 — {date} ({weekday})</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="関東1000人">
<meta name="theme-color" content="#0f1419">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  :root {{
    --bg:#0f1419; --panel:#1a1f2a; --line:#2a3142;
    --text:#e4e7eb; --dim:#8a93a3;
    --accent:#f6c350; --green:#5dd39e; --red:#ef6f6c; --blue:#5dade2;
  }}
  *{{box-sizing:border-box}}
  html,body{{margin:0;height:100%;background:var(--bg);color:var(--text);
    font:12.5px/1.4 -apple-system,BlinkMacSystemFont,"Helvetica Neue","Hiragino Sans","Yu Gothic UI",sans-serif;
    overflow:hidden}}
  /* マップ小・ストーリーフィード大 */
  #app{{display:grid;grid-template-columns:380px 1fr;height:100vh}}
  #left{{display:flex;flex-direction:column;border-right:1px solid var(--line);
    background:var(--panel);overflow:hidden}}
  #map{{flex:0 0 320px;background:#0a0e13;border-bottom:1px solid var(--line)}}
  #leftMeta{{flex:1;overflow-y:auto;padding-bottom:12px}}
  #stories{{overflow-y:auto;background:var(--bg);padding:14px 18px}}
  @media (max-width:900px) {{
    #app{{grid-template-columns:1fr;grid-template-rows:auto 1fr}}
    #left{{border-right:0;border-bottom:1px solid var(--line);max-height:60vh}}
    #map{{flex:0 0 240px}}
  }}
  header{{padding:12px 14px;border-bottom:1px solid var(--line);
    position:sticky;top:0;background:var(--panel);z-index:5}}
  header h1{{margin:0;font-size:13px;font-weight:700;letter-spacing:.03em}}
  header .clock{{font:800 22px ui-monospace,monospace;color:var(--accent);margin:4px 0 2px}}
  header .sub{{color:var(--dim);font-size:10.5px}}
  header .sub a{{color:var(--accent);text-decoration:none}}
  .tiles{{padding:10px 14px;border-bottom:1px solid var(--line);
    display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px}}
  .tile{{padding:6px 8px;background:rgba(255,255,255,.02);border-radius:6px}}
  .tile span{{display:block;color:var(--dim);font-size:9.5px}}
  .tile b{{font:800 16px ui-monospace,monospace;color:var(--text)}}
  .tile.s b{{color:var(--dim)}}
  .tile.w b{{color:var(--green)}}
  .tile.c b{{color:var(--blue)}}
  .tile.l b{{color:var(--accent)}}
  .tile.b b{{color:var(--red)}}
  .legend{{padding:8px 14px;border-bottom:1px solid var(--line);
    display:flex;flex-wrap:wrap;gap:6px 12px;font-size:10px}}
  .legend .key{{display:flex;align-items:center;gap:4px}}
  .legend .dot{{width:9px;height:9px;border-radius:50%}}
  .charts{{padding:10px 14px;border-bottom:1px solid var(--line)}}
  .charts h2{{margin:2px 0 4px;font-size:10px;font-weight:700;color:var(--dim);
    text-transform:uppercase;letter-spacing:.05em}}
  .hist{{width:100%;height:44px}}
  .hist rect{{fill:var(--dim)}}
  .hist rect.past{{fill:var(--accent)}}
  .hist .now{{stroke:var(--green);stroke-width:1.5;stroke-dasharray:2 2}}
  .hist text{{fill:var(--dim);font:9px ui-monospace,monospace}}
  .feed{{padding:0 14px 12px;max-height:340px;overflow:hidden}}
  .feed h2{{margin:10px 0 4px;font-size:11px;font-weight:700;color:var(--accent);
    display:flex;justify-content:space-between}}
  .feed h2 .sum{{color:var(--text);font:700 11px ui-monospace,monospace}}
  .feed-row{{display:grid;grid-template-columns:36px 1fr auto;gap:6px;
    padding:5px 0;border-bottom:1px dotted rgba(255,255,255,.04);font-size:10.5px}}
  .feed-row.new{{animation:slideIn .35s ease-out}}
  @keyframes slideIn{{from{{transform:translateX(-6px);opacity:0}}to{{opacity:1}}}}
  .feed-row .time{{color:var(--dim);font:600 9.5px ui-monospace,monospace}}
  .feed-row .who{{overflow:hidden}}
  .feed-row .who .sku{{display:block;color:var(--text);font-weight:600;font-size:10px;
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .feed-row .who .meta{{display:block;color:var(--dim);font-size:9px}}
  .feed-row .who .why{{display:block;color:var(--accent);font-size:9px;font-style:italic;opacity:.85}}
  .feed-row .price{{color:var(--accent);font:700 10.5px ui-monospace,monospace;text-align:right}}
  .feed-row.impulse{{background:rgba(239,111,108,.06)}}
  .buy-burst{{position:absolute;font-size:14px;pointer-events:none;color:var(--accent);
    text-shadow:0 0 4px rgba(0,0,0,.85);font-weight:700;
    animation:burst 1.1s ease-out forwards}}
  @keyframes burst{{
    0%{{transform:translate(-50%,-50%) scale(.4);opacity:0}}
    25%{{transform:translate(-50%,-110%) scale(1.05);opacity:1}}
    100%{{transform:translate(-50%,-180%) scale(.85);opacity:0}}
  }}
  .focus{{padding:8px 14px;border-bottom:1px solid var(--line)}}
  .focus h2{{margin:0 0 4px;font-size:10px;font-weight:700;color:var(--dim);
    text-transform:uppercase;letter-spacing:.05em}}
  .focus .row{{display:grid;grid-template-columns:8px 1fr;gap:6px;padding:2px 0;font-size:10.5px}}
  .focus .row .d{{width:8px;height:8px;border-radius:50%;margin-top:5px}}
  .focus .row .name{{font-weight:700}}
  .focus .row .name small{{color:var(--dim);font-weight:400;margin-left:4px}}
  .focus .row .act{{color:var(--accent);font-size:10px}}
  /* Story cards */
  .story{{
    background:var(--panel);border:1px solid var(--line);border-radius:10px;
    padding:14px 16px;margin-bottom:14px;
    animation:storyIn .45s ease-out;
  }}
  @keyframes storyIn{{from{{transform:translateY(-4px);opacity:0}}to{{opacity:1}}}}
  .story .head{{display:grid;grid-template-columns:14px 1fr auto;gap:10px;
    align-items:start;padding-bottom:8px;border-bottom:1px solid var(--line);
    margin-bottom:9px}}
  .story .dot{{width:14px;height:14px;border-radius:50%;margin-top:3px}}
  .story .who-name{{font-size:14.5px;font-weight:800}}
  .story .who-name .ages{{color:var(--dim);font-weight:500;font-size:11px;margin-left:6px}}
  .story .who-meta{{color:var(--dim);font-size:10.5px;margin-top:2px}}
  .story .when{{text-align:right;color:var(--accent);font:800 14px ui-monospace,monospace;
    white-space:nowrap}}
  .story .when small{{display:block;color:var(--dim);font:600 9.5px ui-monospace,monospace}}
  .story .blurb{{color:var(--text);font-size:11px;padding:6px 0 4px;font-style:italic}}
  .story .chips{{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px}}
  .story .chip{{font-size:10px;padding:2.5px 8px;border-radius:11px;
    background:rgba(246,195,80,.10);color:var(--accent);border:1px solid rgba(246,195,80,.25)}}
  .story .chip.brand{{background:rgba(93,173,226,.10);color:var(--blue);
    border-color:rgba(93,173,226,.25)}}
  .story .now{{display:flex;align-items:center;gap:8px;padding:8px 0;
    border-top:1px dotted rgba(255,255,255,.08);
    border-bottom:1px dotted rgba(255,255,255,.08)}}
  .story .now-act{{color:var(--green);font-size:12px;font-weight:700}}
  .story .now-tag{{color:var(--dim);font-size:10px}}
  .story .buy-line{{display:grid;grid-template-columns:1fr auto;
    gap:12px;align-items:start;margin-top:10px}}
  .story .buy-sku{{font-size:13px;font-weight:700;color:var(--text);line-height:1.45}}
  .story .buy-meta{{color:var(--dim);font-size:10.5px;margin-top:2px}}
  .story .buy-meta b{{color:var(--text);font-weight:600}}
  .story .buy-price{{font:800 16px ui-monospace,monospace;color:var(--accent);
    white-space:nowrap;text-align:right}}
  .story .buy-price small{{display:block;color:var(--dim);font:600 9.5px sans-serif;
    margin-top:2px}}
  .story .why-title{{font-size:10px;font-weight:700;color:var(--dim);
    text-transform:uppercase;letter-spacing:.05em;margin:10px 0 4px}}
  .story ul.why{{margin:0;padding:0;list-style:none}}
  .story ul.why li{{font-size:11.5px;color:var(--text);padding:3px 0 3px 14px;
    position:relative;line-height:1.5}}
  .story ul.why li::before{{content:'▸';color:var(--accent);position:absolute;left:0;top:3px}}
  .story.imp{{border-left:3px solid var(--red);padding-left:13px}}
  .story .imp-badge{{font-size:9.5px;color:var(--red);font-weight:700;
    margin-left:6px;padding:1.5px 6px;background:rgba(239,111,108,.12);
    border-radius:8px;letter-spacing:.05em}}
  /* Persona hover tooltip */
  .leaflet-tooltip.persona-tip{{
    background:rgba(15,20,25,.96) !important;
    border:1px solid var(--line) !important;
    color:var(--text) !important;
    font:11px/1.5 -apple-system,BlinkMacSystemFont,"Hiragino Sans",sans-serif !important;
    padding:8px 11px !important;
    border-radius:8px !important;
    box-shadow:0 4px 16px rgba(0,0,0,.6) !important;
    pointer-events:none;
    min-width:200px;
  }}
  .leaflet-tooltip.persona-tip::before{{
    border-top-color:rgba(15,20,25,.96) !important;
  }}
  .leaflet-tooltip.persona-tip .tip-name{{color:var(--accent);font-weight:800;font-size:13px}}
  .leaflet-tooltip.persona-tip .tip-meta{{color:var(--dim);font-size:10px;margin-top:2px}}
  .leaflet-tooltip.persona-tip .tip-act{{color:var(--green);font-weight:600;margin-top:4px}}
  .leaflet-tooltip.persona-tip .tip-act .ico{{font-size:13px}}
  .leaflet-tooltip.persona-tip .tip-buy{{
    margin-top:4px;padding-top:4px;border-top:1px dotted var(--line);
    color:var(--accent);font-size:10px}}
</style>
</head>
<body>
<div id="app">
  <div id="left">
    <header>
      <h1>関東 N={n_personas}人 ライブ 監視</h1>
      <div class="clock" id="clock">--:--:--</div>
      <div class="sub" id="subline">{date} ({weekday}) JST · <a href="dashboard.html">📊 集計</a> · <a href="index.html">👁 12人詳細</a></div>
    </header>
    <div id="map"></div>
    <div id="leftMeta">
      <div class="tiles" id="tiles"></div>
      <div class="legend" id="legend"></div>
      <div class="charts">
        <h2>EC 購買 時間帯</h2>
        <svg class="hist" id="hist" viewBox="0 0 360 44" preserveAspectRatio="none"></svg>
      </div>
    </div>
  </div>
  <section id="stories">
    <h2 style="margin:0 0 14px;font-size:13px;color:var(--accent);
      letter-spacing:.04em;display:flex;justify-content:space-between;
      align-items:center">
      <span>💸 購買ストーリー — リアルタイム</span>
      <span id="storiesSum" style="color:var(--text);font:700 12px ui-monospace,monospace"></span>
    </h2>
    <div id="storyList"></div>
  </section>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = {payload_json};

// ===== Map =====
// 関東全域が一望できる広めの初期ズーム
const map = L.map('map', {{zoomControl: true, attributionControl: false,
                           preferCanvas: true}})
  .setView([36.10, 139.75], 9);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  subdomains: 'abcd', maxZoom: 19,
  attribution: '© OpenStreetMap, © CARTO',
}}).addTo(map);

const canvas = L.canvas({{padding: 0.3}});

let currentMinute = 0;   // updated each tick — read by tooltip fn

// Tooltip content: looks up the persona's CURRENT segment + last EC purchase.
const buysByPid = new Map();
DATA.purchases.forEach(b => {{
  if (!buysByPid.has(b.pid)) buysByPid.set(b.pid, []);
  buysByPid.get(b.pid).push(b);
}});

function makeTooltipHTML(p) {{
  const seg = activeSeg(p, currentMinute);
  const act = ACT_LABEL[seg.a] || seg.a;
  const genderJP = p.g === 'M' ? '男性' : '女性';
  // Find most recent purchase up to currentMinute (if any)
  const mine = buysByPid.get(p.i) || [];
  let lastBuy = null;
  for (let i = mine.length - 1; i >= 0; i--) {{
    if (mine[i].m <= currentMinute) {{ lastBuy = mine[i]; break; }}
  }}
  let buyLine = '';
  if (lastBuy) {{
    const hh = String(Math.floor(lastBuy.m / 60)).padStart(2, '0');
    const mm = String(lastBuy.m % 60).padStart(2, '0');
    buyLine = `<div class="tip-buy">💸 ${{hh}}:${{mm}} ${{escapeHtml(lastBuy.sku)}}<br>
       <span style="color:var(--dim)">${{lastBuy.ch}} · ¥${{lastBuy.p.toLocaleString('ja-JP')}}</span></div>`;
  }}
  return `<div>
    <div class="tip-name">${{escapeHtml(p.n)}} <span style="color:var(--dim);font-size:10px;font-weight:400">${{p.a}}歳 ${{genderJP}}</span></div>
    <div class="tip-meta">${{escapeHtml(p.o)}} · ${{escapeHtml(p.pref)}}</div>
    <div class="tip-meta">年収 ¥${{p.inc.toLocaleString('ja-JP')}}</div>
    <div class="tip-act">→ ${{act}}</div>
    ${{buyLine}}
  </div>`;
}}

// One CircleMarker per persona, rendered on shared canvas for perf
const personaState = DATA.personas.map(p => {{
  const marker = L.circleMarker(p.h, {{
    radius: 3.5,         // 少し大きめでホバーしやすく
    weight: 0,
    fillColor: p.c,
    fillOpacity: 0.85,
    renderer: canvas,
    interactive: true,
  }}).addTo(map);
  // Function-based tooltip: re-evaluated each time it opens (live segment)
  marker.bindTooltip(() => makeTooltipHTML(p), {{
    direction: 'top',
    offset: [0, -4],
    opacity: 1,
    className: 'persona-tip',
    sticky: true,         // follows mouse within marker
  }});
  return {{p, marker}};
}});

// ===== Time =====
function tokyoMinutes() {{
  const fmt = new Intl.DateTimeFormat('en-CA', {{
    timeZone: 'Asia/Tokyo',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }});
  const parts = Object.fromEntries(
    fmt.formatToParts(new Date()).map(x => [x.type, x.value])
  );
  const hour = parseInt(parts.hour), minute = parseInt(parts.minute),
        second = parseInt(parts.second);
  const m = hour * 60 + minute + second / 60.0;
  return {{minutes: m, clock: `${{parts.hour}}:${{parts.minute}}:${{parts.second}}`}};
}}

// ===== Position lookup =====
function activeSeg(persona, minute) {{
  const segs = persona.seg;
  for (let i = 0; i < segs.length; i++) {{
    if (minute < segs[i].e) {{
      return minute >= segs[i].s ? segs[i] : segs[Math.max(0, i-1)];
    }}
  }}
  return segs[segs.length - 1];
}}

function positionFor(persona, minute) {{
  const seg = activeSeg(persona, minute);
  // train (commute): lerp between home and workplace by time fraction in segment.
  // morning train: home → work. evening train: work → home.
  if (seg.m === 'train' && persona.w) {{
    const f = (minute - seg.s) / Math.max(1, seg.e - seg.s);
    // Heuristic: if seg.s < 12*60, morning commute (h → w), else evening (w → h)
    const morning = seg.s < 12 * 60;
    const A = morning ? persona.h : persona.w;
    const B = morning ? persona.w : persona.h;
    return [A[0] + (B[0]-A[0]) * f, A[1] + (B[1]-A[1]) * f];
  }}
  // work/wfh_work: at workplace
  if ((seg.a === 'work' || seg.a === 'wfh_work') && persona.w) {{
    return persona.w;
  }}
  // study: at student commute target if exists
  if (seg.a === 'study_home' && persona.w) {{
    return persona.w;
  }}
  // Otherwise: home
  return persona.h;
}}

// ===== Aggregates =====
const ACT_GROUP = {act_group_js};

// ===== Burst layer =====
const burstSeen = new Set();
function spawnBurst(lat, lng, price) {{
  const pt = map.latLngToContainerPoint([lat, lng]);
  const el = document.createElement('div');
  el.className = 'buy-burst';
  el.style.left = pt.x + 'px';
  el.style.top = pt.y + 'px';
  el.textContent = '💸¥' + Math.round(price / 100) * 100;
  document.getElementById('map').appendChild(el);
  setTimeout(() => el.remove(), 1200);
}}

// ===== Legend =====
{{
  const legend = document.getElementById('legend');
  legend.innerHTML = DATA.template_legend.map(([id, label, color]) =>
    `<div class="key"><div class="dot" style="background:${{color}}"></div>${{label}}</div>`
  ).join('');
}}

const ACT_LABEL = {act_label_js};

function escapeHtml(s) {{
  return String(s).replace(/[&<>"']/g, c => ({{
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }}[c]));
}}

// ===== Update loop =====
function update() {{
  const tk = tokyoMinutes();
  const minute = tk.minutes;
  currentMinute = minute;   // expose to tooltip closure
  document.getElementById('clock').textContent = tk.clock + ' JST';

  // Counters
  let sleep = 0, home = 0, work = 0, leisure = 0, commute = 0, out = 0, study = 0;
  // Update all markers
  for (let i = 0; i < personaState.length; i++) {{
    const {{p, marker}} = personaState[i];
    const seg = activeSeg(p, minute);
    const pos = positionFor(p, minute);
    marker.setLatLng(pos);

    const g = ACT_GROUP[seg.a] || 'home';
    if      (g === 'sleep')   sleep++;
    else if (g === 'work')    work++;
    else if (g === 'commute') commute++;
    else if (g === 'leisure') leisure++;
    else if (g === 'study')   study++;
    else if (g === 'out')     out++;
    else                       home++;

    // Dim sleepers
    const newOpacity = (g === 'sleep') ? 0.25 : 0.85;
    if (marker.options.fillOpacity !== newOpacity) {{
      marker.setStyle({{fillOpacity: newOpacity}});
    }}
  }}

  // Purchase aggregation up to current minute
  let buys = 0, spend = 0, impulse = 0;
  const hourly = new Array(24).fill(0);
  for (const b of DATA.purchases) {{
    if (b.m <= minute) {{
      buys++; spend += b.p; if (b.imp) impulse++;
      hourly[Math.floor(b.m / 60)]++;
      const key = `${{b.pid}}-${{b.m}}`;
      if ((minute - b.m) <= 0.6 && !burstSeen.has(key)) {{
        spawnBurst(b.lat, b.lng, b.p);
        burstSeen.add(key);
      }}
    }}
  }}

  // Render tiles
  document.getElementById('tiles').innerHTML = `
    <div class="tile s"><span>💤就寝</span><b>${{sleep}}</b></div>
    <div class="tile w"><span>💻勤務</span><b>${{work}}</b></div>
    <div class="tile c"><span>🚃通勤</span><b>${{commute}}</b></div>
    <div class="tile"><span>🏠家事</span><b>${{home}}</b></div>
    <div class="tile l"><span>🛋自由</span><b>${{leisure}}</b></div>
    <div class="tile b"><span>💸購買累計</span><b>${{buys}}</b></div>`;

  // Render histogram
  {{
    const max = Math.max(1, ...hourly);
    const W = 360, H = 44, BW = W / 24;
    const ch = Math.floor(minute / 60);
    const bars = hourly.map((v, i) => {{
      const h = (v / max) * (H - 10);
      const isPast = i <= ch;
      return `<rect class="${{isPast ? 'past' : ''}}" x="${{i*BW + 0.5}}" y="${{H - h - 10}}" width="${{BW - 1}}" height="${{h}}"/>`;
    }}).join('');
    const labels = [0, 6, 12, 18, 23].map(h =>
      `<text x="${{h*BW + BW/2}}" y="${{H - 1}}" text-anchor="middle">${{h}}</text>`
    ).join('');
    const now = `<line class="now" x1="${{ch * BW + BW/2}}" y1="0"
                                       x2="${{ch * BW + BW/2}}" y2="${{H-10}}"/>`;
    document.getElementById('hist').innerHTML = bars + now + labels;
  }}

  // Render rich story cards (newest 12)
  const upToNow = DATA.purchases.filter(b => b.m <= minute);
  upToNow.sort((a, z) => z.m - a.m);
  const wantKeys = upToNow.slice(0, 12).map(b => `${{b.pid}}-${{b.m}}`);
  const storyList = document.getElementById('storyList');
  // Remove stale
  Array.from(storyList.children).forEach(c => {{
    if (!wantKeys.includes(c.dataset.key)) c.remove();
  }});
  // Add / reorder
  upToNow.slice(0, 12).forEach((b, idx) => {{
    const key = `${{b.pid}}-${{b.m}}`;
    let card = storyList.querySelector(`[data-key="${{key}}"]`);
    if (!card) {{
      const p = DATA.personas[b.pid];
      const seg = activeSeg(p, minute);
      const actLabel = ACT_LABEL[b.act] || ACT_LABEL[seg.a] || b.act;
      const hh = String(Math.floor(b.m / 60)).padStart(2, '0');
      const mm = String(b.m % 60).padStart(2, '0');
      const genderJP = p.g === 'M' ? '男性' : '女性';

      const interestChips = (p.interests || []).map(x =>
        `<span class="chip">${{escapeHtml(x)}}</span>`).join('');
      const brandChips = (p.brands || []).map(x =>
        `<span class="chip brand">${{escapeHtml(x.name)}} ${{x.score >= 0.85 ? '★★★' : x.score >= 0.7 ? '★★' : '★'}}</span>`).join('');
      const whys = (b.whys || []).map(L =>
        `<li>${{escapeHtml(L)}}</li>`).join('');

      const impBadge = b.imp
        ? `<span class="imp-badge">💥 衝動</span>`
        : `<span class="imp-badge" style="color:var(--green);background:rgba(93,211,158,.10)">🛒 計画</span>`;

      card = document.createElement('div');
      card.className = 'story' + (b.imp ? ' imp' : '');
      card.dataset.key = key;
      card.innerHTML = `
        <div class="head">
          <div class="dot" style="background:${{p.c}}"></div>
          <div>
            <div class="who-name">${{escapeHtml(p.n)}}<span class="ages">${{p.a}}歳・${{genderJP}}</span></div>
            <div class="who-meta">${{escapeHtml(p.o)}} ・ ${{escapeHtml(p.pref)}} ・ 年収 ¥${{p.inc.toLocaleString('ja-JP')}}</div>
          </div>
          <div class="when">${{hh}}:${{mm}}<small>${{impBadge}}</small></div>
        </div>

        <div class="blurb">"${{escapeHtml(p.blurb || '')}}"</div>
        <div class="chips">${{interestChips}}</div>
        <div class="chips">${{brandChips}}</div>

        <div class="now">
          <span class="now-act">→ ${{actLabel}}</span>
          <span class="now-tag">の最中に</span>
        </div>

        <div class="buy-line">
          <div>
            <div class="buy-sku">${{escapeHtml(b.sku)}}</div>
            <div class="buy-meta"><b>${{b.ch}}</b> ・ ${{b.cat}}</div>
          </div>
          <div class="buy-price">¥${{b.p.toLocaleString('ja-JP')}}<small>${{b.ch}}</small></div>
        </div>

        <div class="why-title">💡 なぜこのタイミングで買ったか</div>
        <ul class="why">${{whys || `<li>${{escapeHtml(b.why || '')}}</li>`}}</ul>
      `;
    }}
    // Maintain order
    if (storyList.children[idx] !== card) {{
      storyList.insertBefore(card, storyList.children[idx] || null);
    }}
  }});
  document.getElementById('storiesSum').textContent =
    `本日 ${{buys}}件 / ¥${{spend.toLocaleString('ja-JP')}}`;
}}

setInterval(update, 1000);
update();
</script>
</body>
</html>
"""


def render(payload: dict[str, Any], out_path: Path) -> None:
    act_group_js = json.dumps(ACT_GROUP, ensure_ascii=False)
    # Reuse activity labels from monitor (subset)
    act_label = {
        "sleep": "💤 睡眠中",
        "morning_routine": "🪥 朝の支度",
        "morning_routine_w_baby": "🪥 朝の支度 (育児)",
        "morning_routine_w_kids": "🪥 朝の支度 (子供と)",
        "breakfast_home": "🍞 朝食",
        "family_time": "👨‍👩‍👧 家族時間",
        "childcare": "🍼 育児",
        "housework": "🧺 家事",
        "leisure": "🛋 くつろぎ",
        "errands": "📋 用事",
        "train": "🚃 通勤中",
        "work": "💻 勤務中",
        "wfh_work": "🏠 在宅勤務中",
        "lunch_home": "🍱 ランチ",
        "lunch_home_w_kids": "🍱 ランチ (子供と)",
        "dinner_home": "🍳 夕食",
        "instagram_scroll": "📱 SNS",
        "tv_time": "📺 TV",
        "wind_down": "🛀 リラックス",
        "study_home": "📚 学業",
    }
    html = HTML_TEMPLATE.format(
        n_personas=payload["n_personas"],
        date=payload["date"],
        weekday=payload["weekday_jp"],
        payload_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        act_group_js=act_group_js,
        act_label_js=json.dumps(act_label, ensure_ascii=False),
    )
    out_path.write_text(html, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--date", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("out/live-1000.html"))
    args = ap.parse_args()

    if args.date:
        d = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        d = datetime.now(ZoneInfo("Asia/Tokyo")).date()

    print(f"Generating LIVE cohort: N={args.n} for {d.isoformat()}...")
    payload = build(args.n, d, seed=args.seed)
    print(f"  → {payload['n_personas']} personas, "
          f"{payload['n_purchases']} purchases, "
          f"¥{payload['total_spend']:,} total")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    render(payload, args.out)
    size_kb = args.out.stat().st_size / 1024
    print(f"  → {args.out} ({size_kb:.0f}KB)")


if __name__ == "__main__":
    main()
