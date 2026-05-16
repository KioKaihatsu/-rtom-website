# Virtual Human PoC

仮想人格に環境変数（時刻・天候・気温・曜日）を与え、1日の行動と
マーケティング接触をシミュレートする最小プロトタイプ。

## 構成

| ファイル | 役割 |
| --- | --- |
| `persona.py` | 人格定義（Big Five・収入・ブランド嗜好・メディア配分） |
| `environment.py` | 世界モデル（時刻進行、気温日内変動、天気抽選） |
| `simulator.py` | 1時間刻みの意思決定ループと接点ログ出力 |
| `out/` | 実行結果 JSON（persona / events / summary） |

## 実行

```bash
cd experiments/virtual-human
python3 simulator.py
```

## 設計メモ

- 意思決定は「行動候補ごとにスコア付け→最大値を選択」の rule-based。
  時間帯バイアス・内部状態（空腹/疲労/ストレス）・性格・環境・予算で加点減点する。
- 各行動には `ACTIONS` テーブルで状態変化と費用が定義され、選択後に
  `state` を更新する。
- 一部の行動は `TOUCHPOINTS` でチャネル＋候補ブランドにマッピングされ、
  人格の `brand_affinity` を重みにブランド露出を抽選する。

## Claude API への差し替え

`decide_action(persona, world, rng)` を以下のようなプロンプトに置き換えれば、
LLM ベースの行動選択になる：

```python
prompt = f"""
あなたは以下の人物です。
{json.dumps(persona.snapshot(), ensure_ascii=False)}

現在の環境:
{json.dumps(world.snapshot(), ensure_ascii=False)}

次の1時間にとる行動を ACTIONS から1つ選び、理由を50字以内で添えて
JSON で返してください。
"""
```

プロンプトキャッシュで `persona.snapshot()` を固定ブロックにすれば
24 ティック × 多数のペルソナでもコスト効率が良い。

## 次の拡張候補

1. **ペルソナ生成器** — 統計局データを seed に N 人分を自動生成
2. **広告露出インジェクタ** — シミュレーション中に施策を投入し反応を観測
3. **記憶レイヤ** — 過去の購買・接触をベクタDBに蓄積して長期効果を測定
4. **キャリブレーション** — 実 POS/行動ログとのKLダイバージェンス最小化
