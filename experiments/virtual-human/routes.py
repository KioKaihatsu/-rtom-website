"""Real Tokyo station / landmark coordinates and commute route waypoints.

Coordinates are approximate (within ~50m for stations). Routes are simplified
polylines threading actual stations — not GPS-perfect, but realistic enough
that movement on the map traces the real rail lines.
"""
from __future__ import annotations

# ----- Stations and landmarks -----
STN = {
    # JR山手線 (inner loop, 駒込起点)
    "komagome":      (35.7367, 139.7475),
    "tabata":        (35.7378, 139.7610),
    "nishi_nippori": (35.7322, 139.7669),
    "nippori":       (35.7281, 139.7706),
    "uguisudani":    (35.7207, 139.7783),
    "ueno":          (35.7141, 139.7774),
    "okachimachi":   (35.7077, 139.7748),
    "akihabara":     (35.6984, 139.7731),
    "kanda":         (35.6918, 139.7708),
    "tokyo":         (35.6812, 139.7671),
    "yurakucho":     (35.6749, 139.7634),
    "shimbashi":     (35.6657, 139.7585),
    # JR山手線 (outer loop)
    "sugamo":        (35.7332, 139.7390),
    "otsuka":        (35.7314, 139.7290),
    "ikebukuro":     (35.7295, 139.7110),
    "mejiro":        (35.7212, 139.7064),
    "takadanobaba":  (35.7128, 139.7038),
    "shinokubo":     (35.7011, 139.7000),
    "shinjuku":      (35.6896, 139.7006),
    "yoyogi":        (35.6831, 139.7022),
    "harajuku":      (35.6702, 139.7027),
    "shibuya":       (35.6594, 139.7005),
    # 京浜東北線 (赤羽・川口方面)
    "akabane":       (35.7780, 139.7205),
    "higashi_juujou": (35.7672, 139.7232),
    "oji":           (35.7528, 139.7340),
    "kami_nakazato": (35.7470, 139.7382),
    "kawaguchi":     (35.8076, 139.7204),
    "nishi_kawaguchi": (35.7920, 139.7106),
    # 南北線 (駒込・大手町経由)
    "honkomagome":   (35.7274, 139.7521),
    "todaimae":      (35.7194, 139.7574),
    "korakuen":      (35.7079, 139.7521),
    "iidabashi":     (35.7016, 139.7456),
    "ichigaya":      (35.6911, 139.7355),
    "yotsuya":       (35.6863, 139.7305),
    "nagatacho":     (35.6792, 139.7402),
    "tameike":       (35.6738, 139.7400),
    "roppongi_1":    (35.6678, 139.7385),
    "kamiyacho":     (35.6611, 139.7459),
    # 東急田園都市線 (三軒茶屋→渋谷)
    "sangenjaya":    (35.6438, 139.6705),
    "ikejiri_ohashi": (35.6519, 139.6826),
    # 都営三田線 (大山関連)
    "oyama":         (35.7508, 139.6997),
    "sengoku":       (35.7283, 139.7398),
    # 西武新宿線 (高田馬場経由)
    # ... 早稲田大学キャンパス
    "waseda_campus": (35.7062, 139.7195),
    # 都立駒込病院
    "komagome_hospital": (35.7367, 139.7472),
    # 北区役所
    "kita_ward":     (35.7528, 139.7340),
    # 大手町メガバンク
    "otemachi_bank": (35.6852, 139.7660),
    # 渋谷の広告代理店
    "shibuya_office": (35.6594, 139.7005),
    # 川口工場
    "kawaguchi_factory": (35.8120, 139.7155),
    # 池袋の美容室
    "ikebukuro_salon": (35.7320, 139.7155),
    # 大山の居酒屋
    "oyama_izakaya": (35.7505, 139.6997),
}


# ----- Route polylines (rough path through stations) -----

# 山手線 内回り 駒込→東京 (8駅)
YAMANOTE_KOMAGOME_TO_TOKYO = [
    STN["komagome"], STN["tabata"], STN["nishi_nippori"],
    STN["nippori"], STN["uguisudani"], STN["ueno"],
    STN["okachimachi"], STN["akihabara"], STN["kanda"],
    STN["tokyo"],
]

# 山手線 外回り 駒込→新宿→渋谷
YAMANOTE_KOMAGOME_TO_SHIBUYA = [
    STN["komagome"], STN["sugamo"], STN["otsuka"],
    STN["ikebukuro"], STN["mejiro"], STN["takadanobaba"],
    STN["shinokubo"], STN["shinjuku"], STN["yoyogi"],
    STN["harajuku"], STN["shibuya"],
]

# 京浜東北線 赤羽→王子→田端 (途中下車: 王子)
KEIHIN_AKABANE_TO_OJI = [
    STN["akabane"], STN["higashi_juujou"], STN["oji"],
]

# 京浜東北線 川口→駒込・上野方面 (使わないが定義)
KEIHIN_KAWAGUCHI_TO_TABATA = [
    STN["kawaguchi"], STN["akabane"], STN["higashi_juujou"],
    STN["oji"], STN["kami_nakazato"], STN["tabata"],
]

# 東急田園都市線 三軒茶屋→渋谷 (急行2駅)
DENENTOSHI_SANGENJAYA_TO_SHIBUYA = [
    STN["sangenjaya"], STN["ikejiri_ohashi"], STN["shibuya"],
]

# 三田線 大山→巣鴨→駒込近辺はバスがリアル — 都営三田線板橋区役所前経由は省略
# 都営三田線 大山→巣鴨 (4駅)
MITA_OYAMA_TO_SUGAMO = [
    STN["oyama"],
    (35.7421, 139.7064),  # 板橋区役所前
    (35.7376, 139.7188),  # 新板橋
    (35.7340, 139.7287),  # 西巣鴨
    STN["sugamo"],
]
