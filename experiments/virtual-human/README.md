# Virtual Human PoC — 霜降銀座コホート監視ツール

仮想人格12名（駒込 = 霜降銀座商店街から半径15km圏に分布）に環境変数
（時刻・気温・天気）と性格・収入・嗜好を与え、24時間の動き・収支を
**実地図上で監視** するツール。

## 主成果物

| ファイル | 役割 |
| --- | --- |
| `out/monitor.html` | 自己完結HTML地図モニタ（Leaflet）。ブラウザで開くだけ |
| `out/data.json` | シミュレーション生データ |

HTML を開くと：

- 駒込中心の地図上に12名の現在地が色付きマーカーで表示
- 24時間スライダー＋ ▶/⏸ / 速度切替（1×–32×）
- 右パネルで各人の **行動・現在地・残高・本日収入・本日支出・移動距離** が秒単位更新
- 霜降銀座来訪中は背景ハイライト、RIO 来店中はマーカー黄色＆拡大
- 上部に **コホート集計**（霜降銀座 現在人数 / RIO 現在来店 / 累計収入 / 累計支出）

## 構成

| ファイル | 役割 |
| --- | --- |
| `geo.py` | 霜降銀座原点の距離 / 来訪確率カーブ |
| `places.py` | 実在 POI（駒込病院、大手町、渋谷オフィス…）の lat/lng |
| `persona.py` | Traits / State データクラス（時給は年収から自動算出） |
| `personas.py` | 12名のコホート（駒込/巣鴨/田端/池袋/千石/王子/大山/高田馬場/三軒茶屋/赤羽/西日暮里/川口） |
| `environment.py` | 時刻進行・気温日内変動・天気抽選 |
| `simulator.py` | 行動選択 + 場所解決 + 収支・移動距離計算 |
| `web_export.py` | データを HTML テンプレートに差し込み |
| `monitor.py` | CLI + HTML 両方を出力するエントリポイント |

## 実行

```bash
cd experiments/virtual-human
python3 monitor.py                              # CLI ダッシュボード + out/monitor.html
python3 monitor.py --no-anim                    # CLI のアニメーション省略
python3 monitor.py --no-cli                     # HTML のみ
python3 monitor.py --date 2026-05-18            # 月曜（平日）— 通勤と給与が動く
python3 monitor.py --html /tmp/sat.html         # HTML 出力パス指定
python3 monitor.py --json out/data.json         # JSON も同時出力
```

開く：

```bash
open out/monitor.html        # macOS
xdg-open out/monitor.html    # Linux
```

または、`python3 -m http.server` でホストして `http://localhost:8000/out/monitor.html`。

## モデル要素

### 場所解決（`simulator.resolve_location`）

| 行動 | 場所 |
|---|---|
| sleep, morning_routine, dinner_home, netflix, wind_down, workout, online_shopping | 自宅周辺（小さなジッター） |
| commute (朝8時) | 自宅 → 勤務先 |
| commute (夕18時) | 勤務先 → 自宅 |
| work | 勤務先 |
| wfh_work | 自宅 |
| lunch_out, lunch_konbini, cafe_break | 勤務先の半径120m |
| shopping_apparel | 最寄りの繁華街（池袋/新宿/渋谷から距離選択） |
| dinner_out, grocery | 自宅近所 |
| shimofuri_grocery, shimofuri_stroll | 霜降銀座 |
| shimofuri_dining | Riverbed in Otherworld |

### 収入モデル

- `hourly_wage_jpy = income_jpy_year / (52 * 5 * 8)` 自動算出
- `work` / `wfh_work` 行動1ティック = 時給1時間分が `wallet_jpy` と `earned_today_jpy` に加算
- 退職者・学生・主婦は `works_weekdays=False` で給与発生せず

### 移動距離

- ティック間の (lat, lng) 差分を Haversine（平面近似）で km 換算
- 各人 `distance_km_today` に累積

### 来訪確率（`geo.visit_propensity`）

```
< 1.2km : 1.00            徒歩圏 = 日常使い
1.2-5km : 0.55 * e^-(...)  週末利用
5-10km  : 0.15 * e^-(...)  目的来訪
>10km   : 0.03 * e^-(...)  観光・話題
```

## Claude API への差し替え

`simulator.decide_action(persona, world, rng)` を以下のような Claude 呼び出しに
置き換えれば LLM 駆動になる：

```python
import anthropic

client = anthropic.Anthropic()

def decide_action_llm(persona, world, rng):
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=[{
            "type": "text",
            "text": "あなたは以下の人物です:\n"
                    + json.dumps(persona.snapshot(), ensure_ascii=False)
                    + f"\n行動候補: {list(ACTIONS.keys())}",
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"現在の環境: {json.dumps(world.snapshot(), ensure_ascii=False)}\n"
                       "次の1時間にとる行動を1つ JSON で返してください。"
        }],
    )
    return json.loads(resp.content[0].text)["action"]
```

ペルソナ24時間 × 12人 = 288 推論。Haiku 4.5 + プロンプトキャッシュで
1日数十円のオーダー。

## 既知の単純化

- 1ティック = 1時間（前後の動きはフロントエンドが線形補間）
- 天気は東京一帯で共通（局所性なし）
- 通勤経路は直線（実際の駅・路線を考慮しない）
- ペルソナ間の相互作用なし（家族や友人と同伴は未実装）

## 次の拡張

1. **広告露出インジェクタ** — シミュレーション中に施策を投入して反応を観測
2. **記憶レイヤ** — 過去の購買・接触履歴でリピート率測定
3. **キャリブレーション** — 商店街実 POS / 通行量データで重み調整
4. **N=1000 スケール** — 統計データから自動ペルソナ生成
5. **WebSocket リアルタイム化** — シミュレータが回り続け、HTML が常時購読
