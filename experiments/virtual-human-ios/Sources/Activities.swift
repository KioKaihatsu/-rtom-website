import Foundation

private let activityLabels: [String: String] = [
    "sleep": "💤 睡眠中",
    "morning_routine": "🪥 朝の支度",
    "morning_routine_w_baby": "🪥 朝の支度 (育児)",
    "morning_routine_w_kids": "🪥 朝の支度 (子供と)",
    "breakfast_home": "🍞 朝食 (自宅)",
    "family_time": "👨‍👩‍👧 家族時間",
    "childcare": "🍼 育児",
    "housework": "🧺 家事",
    "leisure": "🛋 くつろぎ",
    "hobby": "🎨 趣味",
    "errands": "📋 用事",
    "errands_home": "📋 用事 (自宅)",
    "walk": "🚶 徒歩移動中",
    "train": "🚃 電車移動中",
    "bus": "🚌 バス移動中",
    "car": "🚗 車移動中",
    "work": "💻 勤務中",
    "wfh_work": "🏠 在宅勤務中",
    "night_shift": "🌙 夜勤勤務中",
    "work_shop": "🍶 営業中 (居酒屋)",
    "shop_prep": "🍶 仕込み",
    "shop_cleanup": "🧽 後片付け",
    "shopping_supply": "📦 仕入れ",
    "class": "📚 授業",
    "study_home": "📖 自習",
    "study_night": "📖 夜の勉強",
    "lunch_home": "🍱 ランチ (自宅)",
    "lunch_konbini": "🍙 ランチ (コンビニ)",
    "lunch_out": "🍱 外食ランチ",
    "lunch_home_w_kids": "🍱 ランチ (子供と)",
    "dinner_home": "🍳 夕食 (自宅)",
    "dinner_out": "🍽 外食ディナー",
    "grocery": "🛒 スーパー",
    "shopping_apparel": "👕 アパレル",
    "instagram_scroll": "📱 SNS",
    "tv_time": "📺 TV鑑賞",
    "wind_down": "🛀 リラックス",
    "shimofuri_grocery": "🥬 霜降銀座で買物",
    "shimofuri_dining": "⭐ Riverbed で食事",
    "shimofuri_stroll": "🚶 商店街さんぽ",
]

private let modeLabels: [String: String] = [
    "stay":  "滞在中",
    "walk":  "🚶 徒歩",
    "train": "🚃 電車",
    "bus":   "🚌 バス",
    "car":   "🚗 車",
]

enum Activities {
    static func label(_ act: String) -> String {
        activityLabels[act] ?? act
    }

    static func modeLabel(_ mode: String) -> String {
        modeLabels[mode] ?? mode
    }

    static let workActs: Set<String> = [
        "work", "wfh_work", "night_shift",
        "work_shop", "shop_prep", "shop_cleanup",
    ]

    static func isWorking(_ act: String) -> Bool {
        workActs.contains(act)
    }
}
