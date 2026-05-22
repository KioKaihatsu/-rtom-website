"""EC 購買イベント生成器（拡張版）。

各仮想人格に対して、当日プラウシブルな購買イベントを生成する。SKU は
実商品名・実価格帯ベース、購入理由は時刻・行動文脈・性格から推定。
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import date as date_t
from typing import Any


# ----------------------------------------------------------------------------
# Channel meta
# ----------------------------------------------------------------------------

EC_CHANNELS_META: dict[str, dict[str, Any]] = {
    "Amazon":            {"trust": "broad",    "vibe": "便利"},
    "楽天市場":            {"trust": "30+",     "vibe": "ポイント"},
    "Yahoo!ショッピング":  {"trust": "40+",     "vibe": "ポイント"},
    "メルカリ":           {"trust": "20-35",   "vibe": "中古"},
    "ZOZOTOWN":          {"trust": "20-30",   "vibe": "ファッション"},
    "Uniqlo online":     {"trust": "broad",   "vibe": "定番"},
    "MUJI passport":     {"trust": "broad",   "vibe": "シンプル"},
    "SHEIN":             {"trust": "teens",   "vibe": "激安"},
    "iHerb":             {"trust": "health",  "vibe": "海外"},
    "BUYMA":             {"trust": "luxury",  "vibe": "海外ブランド"},
    "Apple":             {"trust": "tech",    "vibe": "正規"},
    "Yodobashi.com":     {"trust": "broad",   "vibe": "ポイント還元"},
    "honto":             {"trust": "40+",     "vibe": "本"},
    "Oisix":             {"trust": "30-50女", "vibe": "宅配食材"},
    "メチャカリ":          {"trust": "20-30女", "vibe": "サブスク"},
}

# ----------------------------------------------------------------------------
# SKU catalog: (sku, price_min, price_max, default_reason)
# Channels reference these categories.
# ----------------------------------------------------------------------------

CATALOG: dict[tuple[str, str], list[tuple[str, int, int, str]]] = {
    # ---------- 日用品 ----------
    ("Amazon", "日用品"): [
        ("エリエール 消臭+ トイレットペーパー 12ロール ダブル", 580, 780, "ストック切れ"),
        ("アタック ZERO 抗菌プラス 詰替 720g", 380, 480, "ストック切れ"),
        ("クイックル ワイパー 立体吸着 ウェット 32枚", 880, 1180, "リピート"),
        ("Mr.CLEAN マジックリン キッチン用 400ml", 280, 380, "切らしそう"),
        ("LION クリニカ アドバンテージ ハミガキ 130g x 3", 980, 1280, "まとめ買い"),
        ("ピジョン 親子で使える泡シャンプー 詰替 350ml", 680, 880, "リピート"),
        ("ファブリーズ 衣類消臭スプレー 370ml x 2", 880, 1180, "切らした"),
    ],
    ("楽天市場", "日用品"): [
        ("コストコ カークランド トイレットペーパー 30ロール", 3580, 4280, "まとめ買いお得"),
        ("除菌できるウェットティッシュ 100枚 x 8パック", 1480, 1880, "ポイント10倍"),
    ],
    ("Yahoo!ショッピング", "日用品"): [
        ("レノア 本格消臭 詰替 1320ml", 880, 1080, "PayPayキャンペーン"),
        ("除菌洗剤 業務用 4L", 2680, 3280, "PayPay祭"),
    ],
    ("MUJI passport", "日用品"): [
        ("無印良品 ポリプロピレン収納ケース 引出式M", 1490, 1490, "整理用"),
        ("無印良品 アロマオイル ラベンダー 10ml", 1190, 1190, "リラックス"),
        ("無印良品 化粧水 敏感肌用 高保湿 200ml", 690, 690, "リピート"),
    ],

    # ---------- 書籍 / 電子書籍 ----------
    ("Amazon", "書籍"): [
        ("世界一流エンジニアの思考法 (文春新書)", 990, 990, "話題本"),
        ("達人プログラマー 第2版 (オーム社)", 3520, 3520, "技術書"),
        ("ジェイソン流お金の増やし方", 1430, 1430, "投資勉強"),
        ("成瀬は天下を取りに行く (新潮社)", 1705, 1705, "本屋大賞"),
        ("Kindle Paperwhite シグニチャー エディション", 28980, 28980, "読書環境刷新"),
    ],
    ("Amazon", "電子書籍"): [
        ("Kindle 進撃の巨人 最終34巻", 538, 538, "シリーズ完結"),
        ("Kindle 三体III 死神永生 上", 1820, 1820, "話題のSF"),
        ("Kindle ハイキュー!! 文庫版 1-3巻セット", 1980, 1980, "懐かしい"),
    ],
    ("honto", "書籍"): [
        ("夜は短し歩けよ乙女 (角川文庫)", 770, 770, "再読"),
        ("THE THREE-BODY PROBLEM (English)", 2980, 2980, "原書チャレンジ"),
        ("看護管理2025年4月号", 2090, 2090, "仕事用"),
    ],
    ("honto", "電子書籍"): [
        ("hontoポイント 1000円分", 1000, 1000, "次回用ポイント購入"),
    ],

    # ---------- 電化製品・ガジェット ----------
    ("Amazon", "電化製品"): [
        ("Anker PowerLine III USB-C ケーブル 1.8m", 1290, 1290, "ケーブル断線"),
        ("Logicool MX Master 3S ワイヤレスマウス", 14800, 16800, "新調"),
        ("Anker 737 Power Bank 24000mAh 140W", 19990, 21990, "出張用"),
        ("ELECOM USB-C ハブ 7-in-1 4K HDMI", 4980, 6480, "在宅環境"),
        ("Bose QuietComfort Ultra ヘッドホン", 59800, 59800, "通勤集中"),
    ],
    ("Apple", "電化製品"): [
        ("AirPods Pro (第2世代 USB-C)", 39800, 39800, "前のが壊れた"),
        ("Apple Watch Series 10 GPS 42mm", 64800, 64800, "新型発表"),
        ("MagSafe充電器 (1m)", 5980, 5980, "正規品で揃える"),
        ("iPad Pro 11インチ M4 256GB Wi-Fi", 168800, 168800, "クリエイティブ用"),
    ],
    ("Apple", "アクセサリ"): [
        ("AirPods Pro イヤーチップ XSサイズ", 880, 880, "サイズ調整"),
        ("Apple Watch スポーツバンド 42mm ブラック", 6800, 6800, "気分転換"),
    ],
    ("Apple", "サブスク"): [
        ("Apple One 個人プラン 1ヶ月", 1200, 1200, "自動更新"),
        ("iCloud+ 200GB 月額", 400, 400, "容量足りない"),
    ],
    ("Yodobashi.com", "電化製品"): [
        ("Panasonic ナノケアドライヤー EH-NA0J", 33480, 33480, "髪質改善"),
        ("シャープ プラズマクラスター イオン発生機 IG-NX15", 18800, 18800, "花粉対策"),
    ],
    ("Yodobashi.com", "ゲーム"): [
        ("Nintendo Switch 2 ソフト 「マリオカートワールド」", 9980, 9980, "発売日購入"),
        ("PS5 ソフト 「Final Fantasy XVII」", 9680, 9680, "シリーズ続編"),
    ],

    # ---------- 食品 / 飲料 ----------
    ("Amazon", "食品"): [
        ("KIRIN 自然が磨いた天然水 2L x 9本", 1380, 1380, "備蓄"),
        ("カゴメ 野菜一日これ一本 200ml x 24本", 2480, 2880, "朝の野菜"),
        ("カルビー フルグラ 800g x 3", 2580, 2980, "朝食まとめ"),
    ],
    ("Amazon", "コーヒー"): [
        ("STARBUCKS ハウス ブレンド ホール 250g", 1280, 1480, "切らした"),
        ("Blue Bottle Coffee ベラ ドノヴァン 200g", 1900, 2100, "リピート"),
        ("UCC ザ ブレンド 114 レギュラーコーヒー 360g x 6", 4280, 4980, "在宅用ストック"),
        ("猿田彦珈琲 大吉ブレンド ドリップバッグ 10個", 1850, 2050, "気分転換"),
    ],
    ("Oisix", "食品"): [
        ("Kit Oisix 牛肉と野菜のチンジャオロース 2人前", 1580, 1580, "今夜の献立"),
        ("Oisix おうちレストラン 旬の野菜セット", 3980, 3980, "週末まとめ"),
    ],
    ("楽天市場", "食品"): [
        ("北海道産 ホタテ貝柱 1kg 訳あり", 6980, 8480, "ポイント10倍"),
        ("讃岐うどん 半生 太麺 1kg", 1280, 1480, "在庫補充"),
        ("台湾カステラ 6個セット", 2480, 2980, "話題スイーツ"),
    ],

    # ---------- アパレル ----------
    ("Uniqlo online", "アパレル"): [
        ("エアリズム コットン クルーネックT 半袖 (ネイビー L)", 1290, 1290, "夏前リピート"),
        ("感動パンツ ウルトラライト ストレッチ ストレート (ブラック 32inch)", 3990, 3990, "通勤新調"),
        ("ヒートテック クルーネックT 極暖 (グレー M)", 1990, 1990, "冬支度"),
        ("リネンブレンド オープンカラー シャツ 半袖 (オフホワイト L)", 3990, 3990, "週末カジュアル"),
    ],
    ("ZOZOTOWN", "アパレル"): [
        ("BEAMS HEART リネン ジャケット 7号", 14300, 14300, "コーデ用"),
        ("SLY オーバーサイズ スウェット M ベージュ", 8800, 8800, "韓国っぽい"),
        ("nano universe テーパード パンツ 9号", 11000, 11000, "オフィス用"),
        ("steven alan 別注 ボーダー T ホワイト x ネイビー", 7700, 7700, "ZOZO特集"),
    ],
    ("ZOZOTOWN", "シューズ"): [
        ("New Balance 327 グレー x ホワイト 24cm", 12100, 12100, "新色気になって"),
        ("CONVERSE All Star OX 黒 25cm", 6600, 6600, "定番補充"),
    ],
    ("BUYMA", "アパレル"): [
        ("【関税送料込】MM6 Maison Margiela ジャパニーズバッグ S", 38900, 42900, "海外限定色"),
        ("【正規品】POLO Ralph Lauren ケーブルニット 紺 M", 24800, 28800, "クラシック"),
    ],
    ("BUYMA", "ブランド品"): [
        ("【関税込】CELINE トリオンフ キャンバス ミニバッグ", 248000, 268000, "ボーナス記念"),
        ("【海外正規】Bottega Veneta カセット ミニ 黒", 312000, 348000, "30歳記念"),
        ("【関税送料込】Hermès Twilly スカーフ 復刻柄", 23800, 26800, "ギフト用"),
    ],
    ("メルカリ", "アパレル"): [
        ("【美品】UNIQLO x JW Anderson コラボ ニット L", 2800, 4500, "コラボ品再入手"),
        ("【未使用】GU リブニットワンピース ベージュ M", 1200, 2000, "試したい色"),
        ("MUJI 90s ヴィンテージ チノパン 31inch", 2800, 4200, "古着趣味"),
    ],
    ("メルカリ", "中古品"): [
        ("【動作確認済】Sony WH-1000XM4 黒 中古", 18800, 22800, "新品より安い"),
        ("【1度使用】iRobot Roomba i3+ 充電器付き", 32800, 38800, "誰かのお下がり狙い"),
    ],
    ("メルカリ", "ホビー"): [
        ("【美品】鬼滅の刃 全巻セット 1-23巻", 8800, 12800, "一気読み用"),
        ("ポケモンカード SV6a スカーレットex 1BOX", 6800, 8800, "再販分"),
        ("プラモデル HG ガンダムエアリアル 未組立", 1800, 2400, "積みプラ追加"),
    ],
    ("メルカリ", "本"): [
        ("【美品】コンサル一年目が学ぶこと", 800, 1200, "後輩から推薦"),
    ],
    ("SHEIN", "アパレル"): [
        ("SHEIN リブニットトップ ピンク Sサイズ", 980, 1480, "韓国っぽコーデ"),
        ("SHEIN プリーツミニスカート 黒 Sサイズ", 1280, 1780, "TikTok で見て"),
        ("SHEIN オーバーサイズ Tシャツ 白 L", 680, 980, "色違いまとめ"),
        ("SHEIN ニーハイブーツ 黒 M", 2480, 3280, "韓国インスタ"),
    ],
    ("SHEIN", "雑貨"): [
        ("SHEIN シルバーチェーンネックレス 3点セット", 580, 880, "Y2Kコーデ"),
        ("SHEIN スマホケース クリア iPhone15", 380, 580, "可愛いケース欲しい"),
    ],
    ("メチャカリ", "アパレル"): [
        ("メチャカリ ベーシックプラン 月額", 3278, 3278, "サブスクで色々試したい"),
    ],

    # ---------- 化粧品 / コスメ ----------
    ("楽天市場", "化粧品"): [
        ("資生堂 マキアージュ ドラマティック ジェリー BB", 3300, 3850, "ポイント祭"),
        ("ETUDE ティアアイライナー 限定色", 1320, 1650, "新作"),
        ("KOSE 雪肌精 化粧水 200ml", 2860, 3300, "リピート"),
    ],
    ("iHerb", "化粧品"): [
        ("CeraVe フェイシャル モイスチャライザー 89ml", 2280, 2680, "海外定番"),
        ("The Ordinary ナイアシンアミド 10% 30ml", 980, 1280, "話題のスキンケア"),
        ("Burt's Bees リップ バーム ハニー", 480, 680, "リピート"),
    ],
    ("iHerb", "サプリ"): [
        ("California Gold ビタミンC 1000mg 240粒", 1980, 2480, "風邪予防"),
        ("Now Foods マルチビタミン ADAM 90粒", 2280, 2880, "夫向け"),
        ("Solgar 鉄分 25mg 90粒", 1480, 1880, "貧血対策"),
        ("マイプロテイン Impact ホエイ 1kg バニラ", 4280, 4680, "筋トレ補給"),
    ],
    ("iHerb", "食品"): [
        ("California Gold ナッツミックス 907g", 2480, 2980, "間食用"),
    ],

    # ---------- サブスク・デジタル ----------
    ("Amazon", "サブスク"): [
        ("Amazon Prime 年会費 (1年)", 5900, 5900, "年次自動更新"),
        ("Kindle Unlimited 3ヶ月分", 2940, 2940, "読み放題"),
    ],

    # ---------- 家具 ----------
    ("MUJI passport", "家具"): [
        ("無印良品 ポリエステル 綿フランネル こたつ布団", 9990, 9990, "冬支度"),
        ("無印良品 やわらかフィットソファ 1人掛け 用 カバー", 4990, 4990, "気分転換"),
        ("無印良品 体にフィットするソファ 用 カバー", 5990, 5990, "汚れ補充"),
    ],
    ("MUJI passport", "アパレル"): [
        ("無印良品 オーガニックコットン Vネック 半袖T 白 M", 1490, 1490, "夏定番"),
        ("無印良品 縦横ストレッチ 細身パンツ 黒 32inch", 3990, 3990, "通勤用"),
    ],
    ("MUJI passport", "食品"): [
        ("無印良品 不揃いバウム メープル 5袋", 1390, 1390, "おやつストック"),
        ("無印良品 素材を生かしたカレー グリーン", 350, 350, "ストック補充"),
    ],
}


# Fallback SKUs by category (when channel doesn't have specific catalog entry)
FALLBACK_BY_CAT: dict[str, list[tuple[str, int, int, str]]] = {
    "日用品": [("シャンプー詰替", 600, 1000, "切らした")],
    "アパレル": [("Tシャツ", 1200, 4000, "シーズン買い")],
    "化粧品": [("リップクリーム", 600, 1500, "リピート")],
    "食品": [("お菓子セット", 800, 2500, "間食")],
    "書籍": [("文庫本", 700, 1100, "読書")],
    "電化製品": [("USB-C ケーブル", 1000, 2000, "切れた")],
    "コーヒー": [("ドリップコーヒー 18袋", 800, 1500, "切らした")],
    "シューズ": [("スニーカー", 6000, 12000, "新調")],
    "サプリ": [("ビタミン剤", 1000, 2000, "健康")],
    "ホビー": [("コレクション品", 1500, 3500, "趣味")],
    "中古品": [("古着", 1500, 3500, "古着趣味")],
    "本": [("単行本", 1200, 1800, "読書")],
    "ブランド品": [("ブランド小物", 25000, 60000, "ご褒美")],
    "アクセサリ": [("AirPods アクセサリ", 1500, 4000, "気分転換")],
    "サブスク": [("月額サブスク", 800, 2000, "自動更新")],
    "家具": [("収納用品", 1500, 5000, "整理")],
    "雑貨": [("スマホ周辺", 500, 1500, "可愛い")],
    "ゲーム": [("ゲームソフト", 6800, 9800, "新作")],
    "電子書籍": [("Kindle本", 500, 1500, "読書")],
}


# ----------------------------------------------------------------------------
# Reason context modifiers
# ----------------------------------------------------------------------------

REASON_BY_ACTION_BASE: dict[str, str] = {
    "instagram_scroll": "Instagram で広告見て",
    "tv_time":          "TVショッピング見て",
    "train":            "通勤中ふと思い出して",
    "wind_down":        "寝る前に思い立って",
    "family_time":      "家族の話題から",
    "lunch_home":       "ランチ食べながら",
    "dinner_home":      "夕食後にカートを処理",
    "wfh_work":         "仕事の合間に",
    "work":             "勤務中こっそり",
    "morning_routine":  "朝の準備中ふと",
    "morning_routine_w_baby":  "朝の準備中ふと",
    "morning_routine_w_kids":  "朝の準備中ふと",
    "study_home":       "勉強の息抜きに",
    "study_night":      "夜の勉強の合間に",
    "childcare":        "子供の世話の合間に",
    "housework":        "家事中スマホで",
    "hobby":            "趣味の延長で",
    "breakfast_home":   "朝食食べながら",
    "errands":          "用事の合間に",
    "errands_home":     "家で用事の合間に",
    "lunch_home_w_kids":"子供のランチ中に",
}


def _reason_action_phrase(action: str, minute: int) -> str | None:
    """Action label with time-of-day awareness."""
    if action == "leisure":
        if 5 <= minute / 60 < 11:  return "朝のゆっくり時間に"
        if 11 <= minute / 60 < 14: return "お昼のひと息に"
        if 14 <= minute / 60 < 18: return "午後のくつろぎ中に"
        return "夜のリラックス中に"
    return REASON_BY_ACTION_BASE.get(action)


def _seed_for(name: str, target_date: date_t) -> int:
    h = hashlib.sha256(f"{name}|{target_date.isoformat()}".encode()).digest()
    return int.from_bytes(h[:4], "big")


@dataclass(frozen=True)
class Purchase:
    minute: int
    channel: str
    category: str
    sku: str
    price_jpy: int
    impulse: bool
    reason: str
    trigger_action: str
    why_lines: tuple[str, ...] = ()  # 2-3 行の購入理由（性格×文脈×ブランド）

    def to_dict(self) -> dict[str, Any]:
        return {
            "m": self.minute,
            "ch": self.channel,
            "cat": self.category,
            "sku": self.sku,
            "p": self.price_jpy,
            "imp": self.impulse,
            "why": self.reason,
            "act": self.trigger_action,
            "whys": list(self.why_lines),
        }


# ============================================================================
# Persona insight helpers — for rich story cards
# ============================================================================

def personality_blurb(persona) -> str:
    """1行で性格を表す。例: '計画的 / 内向的 / 安定志向'"""
    t = persona.traits
    bits: list[str] = []
    if t.conscientiousness >= 0.72: bits.append("計画的")
    elif t.conscientiousness <= 0.40: bits.append("行き当たりばったり")
    if t.openness >= 0.72: bits.append("好奇心旺盛")
    elif t.openness <= 0.40: bits.append("保守的")
    if t.neuroticism >= 0.60: bits.append("慎重")
    elif t.neuroticism <= 0.35: bits.append("楽観的")
    if t.extraversion >= 0.65: bits.append("外向的")
    elif t.extraversion <= 0.40: bits.append("内向的")
    if t.agreeableness >= 0.75: bits.append("協調的")
    return " / ".join(bits) if bits else "標準的"


def derive_interests(persona) -> list[str]:
    """興味・嗜好を5項目程度。"""
    t = persona.traits
    age = t.age
    income = t.income_jpy_year
    aff = t.brand_affinity
    tpl = getattr(t, "template", "office")
    out: list[str] = []

    # Lifestyle/work
    if tpl == "wfh":          out.append("在宅環境投資")
    if tpl == "student":      out.append("SNSトレンド")
    if tpl == "home":         out.append("家計・子供グッズ")
    if tpl == "retired":      out.append("健康・実用品")
    if tpl == "office" and age < 35: out.append("通勤グッズ")
    if tpl == "healthcare":   out.append("シフト勤務スタイル")

    # Personality-derived
    if t.openness >= 0.72:        out.append("新製品アンテナ")
    if t.conscientiousness >= 0.72: out.append("コスパ重視")
    if t.neuroticism >= 0.60:     out.append("安心リピート派")
    if t.extraversion >= 0.65 and age <= 35: out.append("インスタ映え")
    if t.agreeableness >= 0.75:   out.append("家族・友人優先")

    # Brand affinity
    if aff.get("Amazon", 0) >= 0.85:        out.append("Amazon ヘビー")
    if aff.get("Blue Bottle", 0) >= 0.70:   out.append("スペシャルティ珈琲")
    if aff.get("MUJI", 0) >= 0.70:          out.append("無印シンプル派")
    if aff.get("Uniqlo", 0) >= 0.75:        out.append("ユニクロ常用")
    if aff.get("ZARA", 0) >= 0.60:          out.append("ファストファッション")

    # Income tier
    if income >= 8_000_000:   out.append("プチ贅沢OK")
    elif income < 2_500_000:  out.append("最安値志向")

    # Age-specific
    if age <= 22:             out.append("TikTok 経由トレンド")
    if 25 <= age <= 35 and t.gender == "female": out.append("コスメ・スキンケア")
    if age >= 60:             out.append("健康サプリ・実用品")

    # Dedupe preserving order, max 6
    seen: set = set()
    deduped: list[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            deduped.append(x)
    if not deduped:
        deduped = ["標準的な消費者"]
    return deduped[:6]


def _why_lines(persona, channel: str, category: str, action: str,
               minute: int, impulse: bool) -> list[str]:
    """購入理由を 2-3 行で。性格 × チャネル × タイミング × カテゴリの合成。"""
    t = persona.traits
    age = t.age
    income = t.income_jpy_year
    aff = t.brand_affinity
    lines: list[str] = []

    # --- Timing / action context ---
    h = minute // 60
    if action == "instagram_scroll":
        lines.append("Instagram 広告で目に留まり、その場でタップ")
    elif action == "tv_time":
        lines.append("テレビ視聴中の合間に スマホで購入")
    elif action == "train":
        if h < 12:
            lines.append("朝の通勤電車で広告に触れて即注文")
        else:
            lines.append("帰りの電車で『そういえば』と思い出して買う")
    elif action == "wind_down":
        lines.append("寝る前のスマホ時間にカートを処理")
    elif action == "wfh_work":
        lines.append("在宅勤務の合間、コーヒー1杯のついでに")
    elif action == "work":
        lines.append("勤務中にこっそり (5分の隙間消費)")
    elif action == "leisure":
        if 13 <= h < 17:
            lines.append("週末/午後の余裕時間に整理買い")
        elif 19 <= h < 22:
            lines.append("夕食後のソファ時間に判断")
    elif action in ("morning_routine", "morning_routine_w_baby",
                    "morning_routine_w_kids", "breakfast_home"):
        lines.append("朝食を済ませながら昨夜のカートを確定")
    elif action == "study_home":
        lines.append("勉強の息抜きにスマホを開いてつい")
    elif action == "childcare":
        lines.append("子供の世話の合間、片手でぽちる")
    elif action == "housework":
        lines.append("家事の途中『切らした!』とその場で発注")

    # --- Channel × persona reasoning ---
    if channel == "Amazon" and aff.get("Amazon", 0) >= 0.80:
        lines.append("Amazon ヘビーユーザー、迷ったらまずここ")
    elif channel == "メルカリ" and age <= 35:
        lines.append("中古や限定品をフリマで探す世代")
    elif channel == "楽天市場" and age >= 35:
        lines.append("楽天ポイント還元を狙って週末まとめ買い")
    elif channel == "Yahoo!ショッピング" and age >= 45:
        lines.append("PayPayキャンペーンに反応する層")
    elif channel == "SHEIN" and age <= 22:
        lines.append("TikTok・YouTube 動画から流入する Z 世代")
    elif channel == "ZOZOTOWN" and 20 <= age <= 32:
        lines.append("ファッション特集や別注を欠かさずチェック")
    elif channel == "BUYMA" and income >= 8_000_000:
        lines.append("海外ブランド志向 × 関税込み価格を比較")
    elif channel == "iHerb":
        lines.append("国内では手に入りにくい品を海外通販で")
    elif channel == "Apple":
        lines.append("正規品しか買わないこだわり")
    elif channel == "Uniqlo online":
        lines.append("店頭よりサイズ・色が揃うECを選ぶ")
    elif channel == "MUJI passport":
        lines.append("週末セールとアプリ会員特典に合わせて")
    elif channel == "honto":
        lines.append("書籍は紙派、丸善・ジュンク堂ポイント連携")
    elif channel == "Yodobashi.com":
        lines.append("ヨドバシポイント還元 + 翌日配達")
    elif channel == "Oisix":
        lines.append("時短調理キットで平日の夕食を回す")

    # --- Personality coloring ---
    if impulse and t.openness >= 0.7:
        lines.append("好奇心が背中を押した衝動買い")
    elif not impulse and t.conscientiousness >= 0.75:
        lines.append("リストにあった必須品を計画通り消化")
    elif t.neuroticism >= 0.60 and not impulse:
        lines.append("使い慣れた SKU でリピート、失敗したくない")
    if category == "サブスク":
        lines.append("月次自動更新、判断は1度だけで継続")
    elif category in ("化粧品", "サプリ"):
        lines.append("肌・体調のために定期補充")
    elif category == "アパレル" and impulse:
        lines.append("シーズン色や流行モチーフに反応")
    elif category == "電化製品" and t.openness >= 0.65:
        lines.append("性能比較サイトを読み込んでから")

    # Dedupe and cap
    seen: set = set()
    out: list[str] = []
    for L in lines:
        if L not in seen:
            seen.add(L)
            out.append(L)
    return out[:3]


def _frequency(persona) -> int:
    t = persona.traits
    base = t.brand_affinity.get("Amazon", 0.4) * 7
    if t.age >= 60:
        base *= 0.4
    if t.openness >= 0.7:
        base *= 1.25
    if t.work_from_home:
        base *= 1.15
    # Cap daily EC purchases by income tier (a student doesn't buy 7 things/day)
    income = t.income_jpy_year
    if income < 1_500_000:
        cap = 2
    elif income < 3_000_000:
        cap = 4
    elif income < 5_000_000:
        cap = 5
    elif income < 8_000_000:
        cap = 7
    else:
        cap = 10
    return max(0, min(cap, round(base)))


def _eligible_channels(persona) -> list[tuple[str, float]]:
    t = persona.traits
    age = t.age
    income = t.income_jpy_year
    aff = t.brand_affinity
    out: list[tuple[str, float]] = [
        ("Amazon",            aff.get("Amazon", 0.4)),
        ("楽天市場",            0.6 if 28 <= age <= 55 else 0.2),
        ("Yahoo!ショッピング",   0.45 if age >= 45 else 0.15),
        ("メルカリ",            0.55 if 18 <= age <= 35 else 0.15),
        ("Uniqlo online",      aff.get("Uniqlo", 0.4)),
        ("MUJI passport",      aff.get("MUJI", 0.3)),
        ("honto",              0.30 if age >= 40 else 0.10),
    ]
    if 18 <= age <= 35:
        out.append(("ZOZOTOWN",
                    aff.get("ZARA", 0.3) + aff.get("Uniqlo", 0.3) * 0.5))
    if age <= 22:
        out.append(("SHEIN", 0.70))
    if t.gender == "female" or age <= 35:
        out.append(("iHerb", 0.25))
    if income >= 7_000_000:
        out.append(("BUYMA", 0.30))
    if t.openness >= 0.65 and income >= 5_000_000:
        out.append(("Apple", 0.40))
    if t.openness >= 0.55 and age <= 45:
        out.append(("Yodobashi.com", 0.30))
    if 28 <= age <= 50 and t.gender == "female":
        out.append(("Oisix", 0.30))
    if 20 <= age <= 32 and t.gender == "female":
        out.append(("メチャカリ", 0.20))
    return out


_HIGH = {
    "leisure", "instagram_scroll", "wind_down", "tv_time",
    "family_time", "breakfast_home", "dinner_home", "study_home",
    "hobby",
}
_MED = {
    "morning_routine", "morning_routine_w_baby", "morning_routine_w_kids",
    "errands", "errands_home", "childcare", "housework",
    "lunch_home", "lunch_home_w_kids",
}
_WORK = {"work", "wfh_work"}


def _timing_pool(segments: list[dict]) -> list[tuple[int, str, int]]:
    """Return list of (minute, action, weight) candidates for purchases."""
    out: list[tuple[int, str, int]] = []
    for seg in segments:
        if seg["act"] == "sleep":
            continue
        if seg["mode"] == "train":
            w = 4
        elif seg["act"] in _HIGH:
            w = 6
        elif seg["act"] in _MED:
            w = 2
        elif seg["act"] in _WORK:
            w = 1
        else:
            w = 0
        if w > 0:
            for m in range(seg["s"], seg["e"], 5):
                out.append((m, seg["act"], w))
    return out


def _category_for(channel: str, rng: random.Random) -> str | None:
    """Pick a category for this channel from the catalog."""
    cats = [c for (ch, c) in CATALOG.keys() if ch == channel]
    if not cats:
        return None
    return rng.choice(cats)


def _pick_sku(channel: str, category: str, persona, rng: random.Random
              ) -> tuple[str, int, str]:
    """Pick a specific SKU. Returns (sku, price, default_reason)."""
    pool = CATALOG.get((channel, category)) or FALLBACK_BY_CAT.get(category, [])
    if not pool:
        return (f"{category} 商品", 1000, "購入")
    # Filter by income tier — drop SKUs too expensive for low-income personas
    income = persona.traits.income_jpy_year
    affordable = [
        x for x in pool
        if x[1] <= (income / 200)  # rough rule: max ~0.5% of annual income
    ]
    if not affordable:
        affordable = sorted(pool, key=lambda x: x[1])[:max(1, len(pool) // 2)]
    sku, pmin, pmax, default_reason = rng.choice(affordable)
    price = rng.randint(pmin, pmax)
    return sku, price, default_reason


def _reason_for(default_reason: str, action: str, minute: int, persona,
                rng: random.Random) -> str:
    """Combine SKU default reason with the action context."""
    t = persona.traits
    parts: list[str] = []
    action_phrase = _reason_action_phrase(action, minute)
    if action_phrase:
        parts.append(action_phrase)
    # Personality flavor
    if t.openness >= 0.8 and rng.random() < 0.4:
        parts.append("新製品が気になって")
    elif t.conscientiousness >= 0.75 and rng.random() < 0.3:
        parts.append("計画通り")
    elif t.neuroticism >= 0.55 and rng.random() < 0.3:
        parts.append("安心のリピート")
    parts.append(default_reason)
    # Dedupe while preserving order
    seen = set()
    out = []
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return " / ".join(out[:2])  # combine at most 2 phrases


def generate_purchases(
    persona, schedule_segments: list[dict], target_date: date_t
) -> list[Purchase]:
    seed = _seed_for(persona.traits.name, target_date)
    rng = random.Random(seed)
    n = _frequency(persona)
    if n == 0:
        return []
    channels = _eligible_channels(persona)
    if not channels:
        return []
    ch_names, ch_weights = zip(*channels)
    timing = _timing_pool(schedule_segments)
    if not timing:
        return []

    times = [m for m, _a, _w in timing]
    weights = [w for _m, _a, w in timing]
    action_at: dict[int, str] = {m: a for m, a, _w in timing}

    purchases: list[Purchase] = []
    used: set[int] = set()
    attempts = 0
    while len(purchases) < n and attempts < n * 5:
        attempts += 1
        channel = rng.choices(ch_names, weights=ch_weights, k=1)[0]
        category = _category_for(channel, rng)
        if not category:
            continue
        sku, price, default_reason = _pick_sku(channel, category, persona, rng)
        # Time
        for _try in range(8):
            minute = rng.choices(times, weights=weights, k=1)[0]
            if minute not in used:
                break
        used.add(minute)
        action = action_at.get(minute, "leisure")
        impulse = action in {"instagram_scroll", "tv_time", "leisure", "wind_down"} \
                  or any(seg["s"] <= minute < seg["e"] and seg["mode"] == "train"
                         for seg in schedule_segments)
        reason = _reason_for(default_reason, action, minute, persona, rng)
        whys = _why_lines(persona, channel, category, action, minute, impulse)
        purchases.append(Purchase(
            minute=minute,
            channel=channel,
            category=category,
            sku=sku,
            price_jpy=price,
            impulse=impulse,
            reason=reason,
            trigger_action=action,
            why_lines=tuple(whys),
        ))
    purchases.sort(key=lambda p: p.minute)
    return purchases
