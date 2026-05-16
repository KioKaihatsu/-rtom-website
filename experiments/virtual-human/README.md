# Virtual Human PoC — 霜降銀座コホート監視ツール

仮想人格12名（駒込 = 霜降銀座商店街から半径15km圏に分布）に環境変数
（時刻・気温・天気・湿度）と性格・収入・嗜好を与え、24時間の行動を
シミュレートして霜降銀座および "Riverbed in Otherworld" への接触を観察するツール。

## 構成

| ファイル | 役割 |
| --- | --- |
| `geo.py` | 霜降銀座原点の距離計算 / 来訪確率カーブ |
| `persona.py` | 人格と内部状態のデータクラス |
| `personas.py` | 12名のコホート（駒込/巣鴨/田端/池袋/千石/王子/大山/高田馬場/三軒茶屋/赤羽/西日暮里/川口） |
| `environment.py` | 時刻進行・気温日内変動・天気抽選 |
| `simulator.py` | スコアリング型行動選択 + 接点抽出 |
| `monitor.py` | コホート全体の動きを毎時表示する監視CLI |

## 実行

```bash
cd experiments/virtual-human
python3 monitor.py                       # アニメーション付き
python3 monitor.py --no-anim             # 即実行
python3 monitor.py --date 2026-05-18     # 月曜（平日）
python3 monitor.py --no-anim --json out  # JSONも書き出し
```

## 監視ツールの読み方

毎時、12名の現在地・行動・状態（E=energy / H=hunger / S=stress, 0-9）と
支出を表で表示。霜降銀座系の行動は **シアン**、Riverbed in Otherworld 来店候補は
**黄色** でハイライト。

24時間ループ後にダッシュボード：

- **チャネル別接触数** — 霜降銀座は専用カウンタ
- **ブランド露出** — 居酒屋・カフェ・RIO 等
- **🥬 霜降銀座への来訪** — 人 × 時間 × 行動の生ログ
- **⭐ RIO 来店候補** — 営業時間帯と来訪者
- **時間帯ヒートマップ** — 商店街の混雑予測
- **距離 × 来訪** — 距離減衰の検証

## 来訪確率モデル（`geo.visit_propensity`）

```
< 1.2km : 1.00        徒歩圏 = 日常使い
1.2-5km : 0.55 * e^-((d-1.2)/3)   週末・用事ベース
  5-10km: 0.15 * e^-((d-5)/4)     目的地化が必要
   >10km: 0.03 * e^-((d-10)/5)    観光・話題性のみ
```

ペルソナの `brand_affinity["Riverbed in Otherworld"]` を掛け合わせ、
さらに性格・天気・時間帯で加点減点。

## Claude API への差し替え

`simulator.decide_action(persona, world, rng)` を以下のような Claude 呼び出し
で置き換えれば、ルールベース→LLM 駆動になる：

```python
import anthropic

client = anthropic.Anthropic()

def decide_action_llm(persona, world, rng):
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=[
            {
                "type": "text",
                "text": f"あなたは以下の人物です:\n{json.dumps(persona.snapshot(), ensure_ascii=False)}\n"
                        f"行動候補: {list(ACTIONS.keys())}\n"
                        f"必ず候補から1つだけ JSON で返してください: {{\"action\": \"...\"}}",
                "cache_control": {"type": "ephemeral"},  # ペルソナ部分は固定
            }
        ],
        messages=[
            {"role": "user", "content": f"現在の環境: {json.dumps(world.snapshot(), ensure_ascii=False)}"}
        ],
    )
    return json.loads(resp.content[0].text)["action"]
```

ペルソナ24時間 × 12人 = 288 推論。Haiku 4.5 + プロンプトキャッシュなら
1日数十円のオーダーで回せる。

## 既知の単純化

- 個別ペルソナ間の相互作用なし（友人と一緒に食事 等は未実装）
- 天気は全員共通（東京一帯を1セルとして扱う）
- 行動カタログは20種類のみ — 実運用では業種別に拡張
- Big Five と意思決定の結合はヒューリスティック（実データで校正必要）

## 次の拡張

1. **広告露出インジェクタ** — シミュレーション中に施策を投入し反応を観測
2. **記憶レイヤ** — 過去の購買・接触を保持して「リピート率」を測定
3. **キャリブレーション** — 商店街実 POS / 通行量データで重み調整
4. **N=1000 スケール** — ペルソナ自動生成 + 並列実行
