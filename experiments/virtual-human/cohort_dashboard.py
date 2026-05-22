"""1000人コホートの EC 購買アグリゲート HTML ダッシュボード生成器。

Usage:
    python3 cohort_dashboard.py                  # N=1000 / 今日
    python3 cohort_dashboard.py --n 5000         # N=5000
    python3 cohort_dashboard.py --out out/d.html # 出力先指定
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date as date_t, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from cohort_generator import generate_cohort, schedule_template
from ec_events import generate_purchases


def build(n: int, target_date: date_t, seed: int = 42) -> dict[str, Any]:
    """Generate cohort + purchases, return data payload for dashboard."""
    cohort = generate_cohort(n, seed=seed)
    weekend = target_date.weekday() >= 5

    personas_out = []
    all_purchases = []
    for idx, p in enumerate(cohort):
        t = p.traits
        segs = schedule_template(t.template, weekend)
        buys = generate_purchases(p, segs, target_date)
        personas_out.append({
            "id": idx,
            "name": t.name,
            "age": t.age,
            "gender": t.gender,
            "occupation": t.occupation,
            "income": t.income_jpy_year,
            "prefecture": t.prefecture,
            "lat": t.home_lat,
            "lng": t.home_lng,
            "wfh": t.work_from_home,
            "n_buys": len(buys),
            "spend": sum(b.price_jpy for b in buys),
        })
        for b in buys:
            all_purchases.append({
                "pid": idx,
                "name": t.name,
                "age": t.age,
                "gender": t.gender,
                "occ": t.occupation,
                "income": t.income_jpy_year,
                "pref": t.prefecture,
                "m": b.minute,
                "ch": b.channel,
                "cat": b.category,
                "sku": b.sku,
                "p": b.price_jpy,
                "imp": b.impulse,
                "why": b.reason,
            })

    return {
        "date": target_date.isoformat(),
        "n_personas": len(cohort),
        "n_purchases": len(all_purchases),
        "total_spend": sum(p["p"] for p in all_purchases),
        "personas": personas_out,
        "purchases": all_purchases,
        "generated_at": datetime.now(ZoneInfo("Asia/Tokyo"))
                                 .strftime("%Y-%m-%d %H:%M:%S JST"),
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>コホート EC 分析 — N={n_personas} {date}</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0f1419">
<style>
  :root {{
    --bg:#0f1419; --panel:#1a1f2a; --line:#2a3142;
    --text:#e4e7eb; --dim:#8a93a3;
    --accent:#f6c350; --green:#5dd39e; --red:#ef6f6c; --blue:#5dade2;
  }}
  *{{box-sizing:border-box}}
  html,body{{margin:0;background:var(--bg);color:var(--text);
    font:13px/1.5 -apple-system,BlinkMacSystemFont,"Helvetica Neue","Hiragino Sans","Yu Gothic UI",sans-serif}}
  header{{position:sticky;top:0;background:var(--panel);
    border-bottom:1px solid var(--line);padding:14px 24px;z-index:5}}
  header h1{{margin:0;font-size:16px;font-weight:700}}
  header .sub{{color:var(--dim);font-size:11px;margin-top:2px}}
  .container{{max-width:1400px;margin:0 auto;padding:18px 24px 48px}}
  .grid{{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}}
  .card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;
    padding:14px 16px}}
  .card h2{{margin:0 0 10px;font-size:12px;font-weight:700;color:var(--accent);
    letter-spacing:.05em;text-transform:uppercase}}
  .stat{{display:flex;justify-content:space-between;align-items:baseline}}
  .stat b{{font:700 22px ui-monospace,monospace;color:var(--text)}}
  .stat span{{color:var(--dim);font-size:11px}}
  .row{{display:flex;justify-content:space-between;padding:3px 0;
    border-bottom:1px dotted rgba(255,255,255,.05);font-size:11.5px}}
  .row:last-child{{border:0}}
  .row .lbl{{color:var(--text);overflow:hidden;text-overflow:ellipsis;
    white-space:nowrap;max-width:60%}}
  .row .v{{color:var(--accent);font:600 11px ui-monospace,monospace}}
  .row .v2{{color:var(--dim);font:11px ui-monospace,monospace;margin-left:8px}}
  .bar-row{{display:grid;grid-template-columns:120px 1fr 60px;gap:8px;
    align-items:center;padding:3px 0;font-size:11px}}
  .bar-row .bar-bg{{height:14px;background:rgba(255,255,255,.05);position:relative;
    border-radius:2px;overflow:hidden}}
  .bar-row .bar-fg{{height:100%;background:var(--accent);
    border-radius:2px}}
  .bar-row .val{{color:var(--text);font:600 11px ui-monospace,monospace;
    text-align:right}}
  .bar-row .name{{color:var(--text);overflow:hidden;
    text-overflow:ellipsis;white-space:nowrap}}
  .hist-svg{{width:100%;height:120px}}
  .hist-svg .bar{{fill:var(--accent);opacity:.85}}
  .hist-svg .lbl{{fill:var(--dim);font:9.5px ui-monospace,monospace}}
  .hist-svg .axis{{stroke:var(--line);stroke-width:1}}
  .map-svg{{width:100%;height:380px;background:#0a0e13;border-radius:6px}}
  .map-svg .dot{{fill:var(--accent);opacity:.4}}
  .map-svg .lbl{{fill:var(--dim);font:10px ui-monospace,monospace}}
  .filters{{display:flex;gap:8px;flex-wrap:wrap;padding:12px 0;
    border-bottom:1px solid var(--line);margin-bottom:12px}}
  .filters select, .filters input{{
    background:var(--bg);color:var(--text);border:1px solid var(--line);
    border-radius:5px;padding:5px 10px;font-size:11.5px}}
  .filters .count{{margin-left:auto;color:var(--accent);font:700 12px ui-monospace,monospace;align-self:center}}
  table.purchases{{width:100%;border-collapse:collapse;font-size:11.5px}}
  table.purchases th{{position:sticky;top:0;background:var(--panel);
    text-align:left;padding:8px 6px;color:var(--dim);font-weight:600;
    border-bottom:1px solid var(--line);font-size:10.5px;
    text-transform:uppercase;letter-spacing:.04em;cursor:pointer}}
  table.purchases th:hover{{color:var(--accent)}}
  table.purchases td{{padding:7px 6px;border-bottom:1px solid rgba(255,255,255,.03)}}
  table.purchases tr:hover{{background:rgba(255,255,255,.02)}}
  table.purchases .sku{{color:var(--text);font-weight:600;max-width:240px;
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:block}}
  table.purchases .why{{color:var(--dim);font-size:10px;font-style:italic;display:block}}
  table.purchases .price{{color:var(--accent);font:600 11px ui-monospace,monospace;
    text-align:right;white-space:nowrap}}
  table.purchases td.imp::before{{content:'💥 ';color:var(--red)}}
  .full-width{{grid-column:1/-1}}
  .toolbar a, .toolbar button{{
    background:var(--accent);color:#1a1207;border:0;border-radius:5px;
    padding:5px 11px;font:700 11px sans-serif;cursor:pointer;
    text-decoration:none;margin-right:6px}}
</style>
</head>
<body>
<header>
  <h1>コホート EC 分析 — N={n_personas} 人 / {date}</h1>
  <div class="sub" id="subline"></div>
  <div class="sub" style="margin-top:4px">
    <a href="index.html" style="color:var(--accent);text-decoration:none;font-weight:700">👁 12人詳細ライブ</a>
    ·
    <a href="live-1000.html" style="color:var(--accent);text-decoration:none;font-weight:700">🗾 関東1000人ライブ</a>
  </div>
</header>
<div class="container">
  <div class="grid">

    <div class="card">
      <h2>サマリー</h2>
      <div class="stat"><span>ペルソナ</span><b id="s_personas">—</b></div>
      <div class="stat"><span>購買件数</span><b id="s_buys">—</b></div>
      <div class="stat"><span>EC 総額</span><b id="s_spend">—</b></div>
      <div class="stat"><span>平均単価</span><b id="s_avg">—</b></div>
      <div class="stat"><span>1人あたり購買</span><b id="s_per">—</b></div>
      <div class="stat"><span>衝動買い比率</span><b id="s_imp">—</b></div>
    </div>

    <div class="card">
      <h2>チャネル別 (購買件数)</h2>
      <div id="ch_bars"></div>
    </div>

    <div class="card">
      <h2>カテゴリ別 (購買金額)</h2>
      <div id="cat_bars"></div>
    </div>

    <div class="card">
      <h2>時間帯ヒストグラム (購買件数)</h2>
      <svg class="hist-svg" id="hist" viewBox="0 0 400 120" preserveAspectRatio="none"></svg>
    </div>

    <div class="card">
      <h2>年齢層別 EC 行動</h2>
      <div id="age_bars"></div>
    </div>

    <div class="card">
      <h2>都県別 1人あたり EC 額</h2>
      <div id="pref_bars"></div>
    </div>

    <div class="card">
      <h2>職業別 (購買件数)</h2>
      <div id="occ_bars"></div>
    </div>

    <div class="card">
      <h2>所得階層別 平均 EC 額</h2>
      <div id="inc_bars"></div>
    </div>

    <div class="card full-width">
      <h2>関東圏 居住分布 (1ドット=1人)</h2>
      <svg class="map-svg" id="map" viewBox="138.4 35.20 2.45 1.95"
        preserveAspectRatio="xMidYMid meet"></svg>
    </div>

    <div class="card full-width">
      <h2>人気 SKU TOP 20</h2>
      <div id="sku_bars"></div>
    </div>

    <div class="card full-width">
      <h2>購買フィード（フィルター可）</h2>
      <div class="filters">
        <select id="f_ch"><option value="">全チャネル</option></select>
        <select id="f_cat"><option value="">全カテゴリ</option></select>
        <select id="f_pref"><option value="">全都県</option></select>
        <select id="f_age"><option value="">全年齢層</option></select>
        <select id="f_imp"><option value="">衝動/計画 すべて</option><option value="1">衝動買いのみ</option><option value="0">計画購入のみ</option></select>
        <input type="text" id="f_q" placeholder="SKU/人名/理由 を検索"/>
        <div class="count" id="f_count"></div>
        <button onclick="downloadCSV()">CSV ダウンロード</button>
      </div>
      <div style="max-height:520px;overflow:auto">
        <table class="purchases">
          <thead>
            <tr>
              <th data-sort="m">時刻</th>
              <th data-sort="name">人物</th>
              <th data-sort="age">年齢</th>
              <th>性別</th>
              <th data-sort="occ">職業</th>
              <th data-sort="pref">居住</th>
              <th data-sort="ch">チャネル</th>
              <th>カテゴリ</th>
              <th>商品名 / 理由</th>
              <th data-sort="p">価格</th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </div>

  </div>
</div>
<script>
const DATA = {payload_json};

// --- Helpers ---
function yen(n) {{ return '¥' + Math.round(n).toLocaleString('ja-JP'); }}
function pct(a,b) {{ return b ? (100 * a / b).toFixed(1) + '%' : '0%'; }}
function escapeHtml(s) {{
  return String(s).replace(/[&<>"']/g, c => ({{
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }}[c]));
}}

// --- Aggregates ---
const buys = DATA.purchases;
const personas = DATA.personas;

document.getElementById('s_personas').textContent = DATA.n_personas.toLocaleString('ja-JP');
document.getElementById('s_buys').textContent = DATA.n_purchases.toLocaleString('ja-JP');
document.getElementById('s_spend').textContent = yen(DATA.total_spend);
document.getElementById('s_avg').textContent =
  yen(DATA.total_spend / Math.max(1, DATA.n_purchases));
document.getElementById('s_per').textContent =
  (DATA.n_purchases / DATA.n_personas).toFixed(2) + ' 件';
const impCount = buys.filter(b => b.imp).length;
document.getElementById('s_imp').textContent = pct(impCount, buys.length);
document.getElementById('subline').textContent =
  `生成: ${{DATA.generated_at}} · 衝動買い ${{impCount.toLocaleString('ja-JP')}} 件 (${{pct(impCount, buys.length)}})`;

function topN(map, n=10) {{
  return Object.entries(map).sort((a,z) => z[1] - a[1]).slice(0, n);
}}
function topNValue(map, key, n=10) {{
  // map[k] = {{count, spend}}
  return Object.entries(map).sort((a,z) => z[1][key] - a[1][key]).slice(0, n);
}}

function barRow(label, val, max, fmt = yen) {{
  const pctW = Math.round(100 * val / Math.max(1, max));
  return `<div class="bar-row">
    <div class="name">${{escapeHtml(label)}}</div>
    <div class="bar-bg"><div class="bar-fg" style="width:${{pctW}}%"></div></div>
    <div class="val">${{fmt(val)}}</div>
  </div>`;
}}

// Channel breakdown
const chCount = {{}};
const chSpend = {{}};
buys.forEach(b => {{ chCount[b.ch] = (chCount[b.ch]||0)+1; chSpend[b.ch] = (chSpend[b.ch]||0)+b.p; }});
{{
  const top = topN(chCount, 12);
  const max = top[0] ? top[0][1] : 1;
  document.getElementById('ch_bars').innerHTML = top.map(([ch, c]) =>
    barRow(ch, c, max, x => x.toLocaleString('ja-JP') + ' 件')
  ).join('');
}}

// Category breakdown by spend
const catSpend = {{}};
buys.forEach(b => {{ catSpend[b.cat] = (catSpend[b.cat]||0)+b.p; }});
{{
  const top = topN(catSpend, 12);
  const max = top[0] ? top[0][1] : 1;
  document.getElementById('cat_bars').innerHTML = top.map(([c, v]) =>
    barRow(c, v, max)
  ).join('');
}}

// Hourly histogram
const hourly = new Array(24).fill(0);
buys.forEach(b => hourly[Math.floor(b.m / 60)]++);
{{
  const W = 400, H = 120, BW = W / 24;
  const maxH = Math.max(1, ...hourly);
  const bars = hourly.map((v, i) => {{
    const h = (v / maxH) * (H - 24);
    return `<rect class="bar" x="${{i*BW + 1}}" y="${{H - h - 16}}"
      width="${{BW - 2}}" height="${{h}}"/>`;
  }}).join('');
  const labels = [0, 3, 6, 9, 12, 15, 18, 21].map(h =>
    `<text class="lbl" x="${{h*BW + BW/2}}" y="${{H - 2}}" text-anchor="middle">${{h}}</text>`
  ).join('');
  document.getElementById('hist').innerHTML = bars + labels;
}}

// Age group breakdown — count & avg spend
function ageGroup(age) {{
  if (age < 25) return '18-24';
  if (age < 35) return '25-34';
  if (age < 45) return '35-44';
  if (age < 55) return '45-54';
  if (age < 65) return '55-64';
  return '65+';
}}
{{
  const groups = {{}};
  personas.forEach(p => {{
    const g = ageGroup(p.age);
    groups[g] = groups[g] || {{count: 0, buys: 0, spend: 0}};
    groups[g].count++;
    groups[g].buys += p.n_buys;
    groups[g].spend += p.spend;
  }});
  const order = ['18-24','25-34','35-44','45-54','55-64','65+'];
  const max = Math.max(...order.map(g => (groups[g] || {{spend:0}}).spend / Math.max(1, (groups[g]||{{count:1}}).count)));
  document.getElementById('age_bars').innerHTML = order.map(g => {{
    const v = groups[g] || {{count: 0, buys: 0, spend: 0}};
    const avg = v.spend / Math.max(1, v.count);
    return `<div class="bar-row">
      <div class="name">${{g}} <small style="color:var(--dim)">(${{v.count}}人)</small></div>
      <div class="bar-bg"><div class="bar-fg" style="width:${{(avg/max*100)}}%"></div></div>
      <div class="val">${{yen(avg)}}/人</div>
    </div>`;
  }}).join('');
}}

// Prefecture spend/person
{{
  const groups = {{}};
  personas.forEach(p => {{
    groups[p.prefecture] = groups[p.prefecture] || {{count: 0, spend: 0}};
    groups[p.prefecture].count++;
    groups[p.prefecture].spend += p.spend;
  }});
  const arr = Object.entries(groups).map(([k, v]) => [k, v.spend / Math.max(1, v.count), v.count]);
  arr.sort((a, z) => z[1] - a[1]);
  const max = arr[0] ? arr[0][1] : 1;
  document.getElementById('pref_bars').innerHTML = arr.map(([k, v, c]) =>
    `<div class="bar-row">
      <div class="name">${{escapeHtml(k)}} <small style="color:var(--dim)">(${{c}}人)</small></div>
      <div class="bar-bg"><div class="bar-fg" style="width:${{(v/max*100)}}%"></div></div>
      <div class="val">${{yen(v)}}/人</div>
    </div>`
  ).join('');
}}

// Occupation breakdown
{{
  const groups = {{}};
  buys.forEach(b => {{
    groups[b.occ] = groups[b.occ] || {{count:0, spend:0}};
    groups[b.occ].count++;
    groups[b.occ].spend += b.p;
  }});
  const top = topNValue(groups, 'count', 12);
  const max = top[0] ? top[0][1].count : 1;
  document.getElementById('occ_bars').innerHTML = top.map(([k, v]) =>
    barRow(k, v.count, max, x => x.toLocaleString('ja-JP') + ' 件')
  ).join('');
}}

// Income tier breakdown
{{
  const tiers = [
    [0, 2_000_000, '〜200万'],
    [2_000_000, 4_000_000, '200-400万'],
    [4_000_000, 6_000_000, '400-600万'],
    [6_000_000, 8_000_000, '600-800万'],
    [8_000_000, 12_000_000, '800-1200万'],
    [12_000_000, Infinity, '1200万+'],
  ];
  const stats = tiers.map(([min, max, label]) => {{
    const ps = personas.filter(p => p.income >= min && p.income < max);
    const spend = ps.reduce((s,p)=>s+p.spend, 0);
    return {{label, count: ps.length, avg: spend / Math.max(1, ps.length)}};
  }});
  const maxAvg = Math.max(...stats.map(s => s.avg), 1);
  document.getElementById('inc_bars').innerHTML = stats.map(s => `
    <div class="bar-row">
      <div class="name">${{s.label}} <small style="color:var(--dim)">(${{s.count}}人)</small></div>
      <div class="bar-bg"><div class="bar-fg" style="width:${{(s.avg/maxAvg*100)}}%"></div></div>
      <div class="val">${{yen(s.avg)}}</div>
    </div>`
  ).join('');
}}

// Map of homes
{{
  // viewBox: minLng 138.4, minLat 35.20, width 2.45 (Lng), height 1.95 (Lat)
  // Flip lat: y = (minLat + height) - lat = 37.15 - lat
  const dots = personas.map(p =>
    `<circle class="dot" cx="${{p.lng}}" cy="${{37.15 - p.lat + 35.20}}" r="0.012"/>`
  ).join('');
  const labels = [
    [139.69, 37.15 - 35.69 + 35.20, '東京'],
    [139.64, 37.15 - 35.44 + 35.20, '横浜'],
    [139.65, 37.15 - 35.86 + 35.20, '埼玉'],
    [140.12, 37.15 - 35.60 + 35.20, '千葉'],
    [140.45, 37.15 - 36.34 + 35.20, '茨城'],
  ].map(([x, y, t]) => `<text class="lbl" x="${{x}}" y="${{y}}" font-size="0.06">${{t}}</text>`).join('');
  document.getElementById('map').innerHTML = dots + labels;
}}

// Top SKUs
{{
  const skuCount = {{}};
  buys.forEach(b => {{
    skuCount[b.sku] = skuCount[b.sku] || {{count:0, spend:0, ch:b.ch, cat:b.cat}};
    skuCount[b.sku].count++;
    skuCount[b.sku].spend += b.p;
  }});
  const top = topNValue(skuCount, 'count', 20);
  const max = top[0] ? top[0][1].count : 1;
  document.getElementById('sku_bars').innerHTML = top.map(([k, v]) =>
    `<div class="bar-row">
      <div class="name">${{escapeHtml(k)}} <small style="color:var(--dim)">${{v.ch}} · ${{v.cat}}</small></div>
      <div class="bar-bg"><div class="bar-fg" style="width:${{(v.count/max*100)}}%"></div></div>
      <div class="val">${{v.count}}件 · ${{yen(v.spend)}}</div>
    </div>`
  ).join('');
}}

// --- Filter dropdowns
function populate(id, values) {{
  const sel = document.getElementById(id);
  values.sort();
  values.forEach(v => {{
    const opt = document.createElement('option');
    opt.value = v; opt.textContent = v;
    sel.appendChild(opt);
  }});
}}
populate('f_ch', Array.from(new Set(buys.map(b => b.ch))));
populate('f_cat', Array.from(new Set(buys.map(b => b.cat))));
populate('f_pref', Array.from(new Set(buys.map(b => b.pref))));
populate('f_age', ['18-24','25-34','35-44','45-54','55-64','65+']);

const f_ch  = document.getElementById('f_ch');
const f_cat = document.getElementById('f_cat');
const f_pref= document.getElementById('f_pref');
const f_age = document.getElementById('f_age');
const f_imp = document.getElementById('f_imp');
const f_q   = document.getElementById('f_q');

let sortKey = 'm', sortDir = 1, filtered = buys;

function applyFilters() {{
  const ch = f_ch.value, cat = f_cat.value, pref = f_pref.value,
        age = f_age.value, imp = f_imp.value, q = f_q.value.trim().toLowerCase();
  filtered = buys.filter(b => {{
    if (ch && b.ch !== ch) return false;
    if (cat && b.cat !== cat) return false;
    if (pref && b.pref !== pref) return false;
    if (age && ageGroup(b.age) !== age) return false;
    if (imp === '1' && !b.imp) return false;
    if (imp === '0' && b.imp) return false;
    if (q) {{
      const hay = (b.sku + ' ' + b.name + ' ' + b.why).toLowerCase();
      if (!hay.includes(q)) return false;
    }}
    return true;
  }});
  render();
}}

function render() {{
  // Sort
  filtered.sort((a, z) => {{
    const av = a[sortKey], zv = z[sortKey];
    if (av === zv) return 0;
    return (av < zv ? -1 : 1) * sortDir;
  }});
  const slice = filtered.slice(0, 500);  // cap render to 500 rows
  document.getElementById('f_count').textContent =
    `${{filtered.length.toLocaleString('ja-JP')}} 件 (表示 ${{slice.length}}件)`;
  document.getElementById('rows').innerHTML = slice.map(b => {{
    const hh = String(Math.floor(b.m / 60)).padStart(2, '0');
    const mm = String(b.m % 60).padStart(2, '0');
    return `<tr>
      <td>${{hh}}:${{mm}}</td>
      <td>${{escapeHtml(b.name)}}</td>
      <td>${{b.age}}</td>
      <td>${{b.gender === 'male' ? '男' : '女'}}</td>
      <td>${{escapeHtml(b.occ)}}</td>
      <td>${{escapeHtml(b.pref)}}</td>
      <td>${{b.ch}}</td>
      <td>${{b.cat}}</td>
      <td class="${{b.imp ? 'imp' : ''}}">
        <span class="sku">${{escapeHtml(b.sku)}}</span>
        <span class="why">${{escapeHtml(b.why)}}</span>
      </td>
      <td class="price">¥${{b.p.toLocaleString('ja-JP')}}</td>
    </tr>`;
  }}).join('');
}}

[f_ch, f_cat, f_pref, f_age, f_imp].forEach(el => el.addEventListener('change', applyFilters));
f_q.addEventListener('input', applyFilters);

document.querySelectorAll('th[data-sort]').forEach(th => {{
  th.addEventListener('click', () => {{
    const k = th.dataset.sort;
    if (sortKey === k) sortDir = -sortDir;
    else {{ sortKey = k; sortDir = 1; }}
    render();
  }});
}});

function downloadCSV() {{
  const rows = [['minute','hh:mm','name','age','gender','occupation','prefecture',
                 'channel','category','sku','price_jpy','impulse','reason']];
  filtered.forEach(b => {{
    const hh = String(Math.floor(b.m / 60)).padStart(2,'0');
    const mm = String(b.m % 60).padStart(2,'0');
    rows.push([b.m, `${{hh}}:${{mm}}`, b.name, b.age, b.gender, b.occ, b.pref,
               b.ch, b.cat, b.sku, b.p, b.imp ? '1':'0', b.why]);
  }});
  const csv = rows.map(r => r.map(x => `"${{String(x).replace(/"/g, '""')}}"`).join(',')).join('\\n');
  const blob = new Blob(['\\uFEFF' + csv], {{type: 'text/csv;charset=utf-8'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `cohort-purchases-${{DATA.date}}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}}

applyFilters();
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000,
                    help="ペルソナ数 (default 1000)")
    ap.add_argument("--date", default=None,
                    help="対象日 YYYY-MM-DD (default 今日)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("out/dashboard.html"))
    ap.add_argument("--json", type=Path, default=None,
                    help="生データ JSON 出力")
    ap.add_argument("--csv", type=Path, default=None,
                    help="CSV 出力 (purchases / personas を 2 ファイル生成)")
    args = ap.parse_args()

    if args.date:
        d = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        d = datetime.now(ZoneInfo("Asia/Tokyo")).date()

    print(f"Generating cohort: N={args.n} for {d.isoformat()}...")
    payload = build(args.n, d, seed=args.seed)
    print(f"  → {payload['n_personas']} personas, "
          f"{payload['n_purchases']} purchases, "
          f"¥{payload['total_spend']:,} total")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    html = HTML_TEMPLATE.format(
        n_personas=payload["n_personas"],
        date=payload["date"],
        payload_json=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    args.out.write_text(html, encoding="utf-8")
    size_kb = args.out.stat().st_size / 1024
    print(f"  → {args.out} ({size_kb:.0f}KB)")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  → {args.json}")

    if args.csv:
        import csv as _csv
        base = args.csv
        base.parent.mkdir(parents=True, exist_ok=True)
        stem = base.with_suffix("")
        buys_csv = stem.with_name(stem.name + "-purchases.csv")
        people_csv = stem.with_name(stem.name + "-personas.csv")

        with open(buys_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.writer(f)
            w.writerow(["minute", "hh:mm", "name", "age", "gender",
                        "occupation", "prefecture", "income_jpy",
                        "channel", "category", "sku", "price_jpy",
                        "impulse", "reason"])
            for b in payload["purchases"]:
                hh, mm = divmod(b["m"], 60)
                w.writerow([b["m"], f"{hh:02d}:{mm:02d}",
                            b["name"], b["age"],
                            "男" if b["gender"] == "male" else "女",
                            b["occ"], b["pref"], b["income"],
                            b["ch"], b["cat"], b["sku"], b["p"],
                            1 if b["imp"] else 0, b["why"]])

        with open(people_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.writer(f)
            w.writerow(["id", "name", "age", "gender", "occupation",
                        "prefecture", "lat", "lng", "income_jpy", "wfh",
                        "n_purchases_today", "spend_today_jpy"])
            for p in payload["personas"]:
                w.writerow([p["id"], p["name"], p["age"],
                            "男" if p["gender"] == "male" else "女",
                            p["occupation"], p["prefecture"],
                            p["lat"], p["lng"], p["income"],
                            1 if p["wfh"] else 0,
                            p["n_buys"], p["spend"]])
        print(f"  → {buys_csv}  ({len(payload['purchases'])} rows)")
        print(f"  → {people_csv}  ({len(payload['personas'])} rows)")


if __name__ == "__main__":
    main()
