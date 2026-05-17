# 霜降銀座コホート 監視 iOS App

`experiments/virtual-human/` で構築した12人の仮想人格コホートを、iPhone /
iPad 上で **リアルタイム監視** するネイティブ SwiftUI アプリ。

- 地図: **MapKit** (`MapStyle.standard`) で霜降銀座中心の Tokyo を表示
- データ: Python 側で生成した `schedules.json` をバンドル
- 時刻: Asia/Tokyo の wall-clock を 0.5秒ごとに読んで現在区間を表示
- 未来: 表示せず（スクラブで過去には戻れる）

## 必要環境

- macOS + **Xcode 15+** （iOS 17 SDK）
- 動作対象: iOS 17.0 以上 / iPhone & iPad
- 言語: Swift 5.10 / SwiftUI

## ビルド手順 (推奨: XcodeGen 経由)

```bash
brew install xcodegen
cd experiments/virtual-human-ios

# スケジュール JSON を最新化
./generate-schedules.sh

# Xcode プロジェクトを生成
xcodegen generate

# 開く
open VirtualHumanMonitor.xcodeproj
```

Xcode が開いたら：

1. プロジェクトを選択 → `Signing & Capabilities` → `Team` を自分の Apple ID に設定
2. デバイスを iOS シミュレータ (iPhone 15 など) または実機に切り替え
3. ⌘R で実行

## ビルド手順 (XcodeGen を使わない場合)

1. Xcode で **File → New → Project → iOS App** を選択
2. 設定:
   - Product Name: `VirtualHumanMonitor`
   - Bundle Identifier: `jp.kiokaihatsu.virtualhuman.monitor`
   - Interface: **SwiftUI**, Language: **Swift**
   - Minimum deployment: **iOS 17.0**
3. 生成された `ContentView.swift` と `<ProjectName>App.swift` を **削除**
4. このディレクトリの `Sources/*.swift` をすべて **Add Files to "VirtualHumanMonitor"** で追加
5. `Resources/schedules.json` を **Copy items if needed** をオンにして追加（Target Membership にチェック）
6. ⌘R

## 構成

```
experiments/virtual-human-ios/
├── README.md
├── project.yml                       XcodeGen 用マニフェスト
├── generate-schedules.sh             Python → schedules.json 再生成
├── Sources/
│   ├── VirtualHumanMonitorApp.swift  @main エントリ
│   ├── TimeEngine.swift              JST 時刻ドライバ (0.5s tick)
│   ├── Models.swift                  Codable データ構造
│   ├── PayloadLoader.swift           schedules.json ロード
│   ├── SegmentLogic.swift            時刻→区間→位置の計算
│   ├── ColorHex.swift                "#rrggbb" → SwiftUI.Color
│   ├── Activities.swift              行動・モードの絵文字ラベル
│   ├── ContentView.swift             マップ + 下シート
│   ├── MapView.swift                 MapKit + マーカー + 軌跡
│   ├── HeaderView.swift              JST 時計
│   ├── PersonaSheet.swift            下から引き上げるシート
│   ├── StatsBar.swift                就寝/勤務/RIO 等の集計
│   └── PersonaCardView.swift         個人カード行
└── Resources/
    ├── Info.plist
    └── schedules.json                Python から生成 (107KB)
```

## アプリ画面

- **上部 (Header)**: JST 時計、曜日。`LIVE` バッジで現在再生中であることを表示
- **地図 (全画面下層)**: 霜降銀座を中心に12人を色付きドットで表示。
  移動中はパルス、夜勤など睡眠時は半透明、RIO 来店中はオレンジ枠拡大
- **下シート (ドラッグで高さ調整)**:
  - スクラブバー — 当日の過去時刻にスクラブ可能（未来不可）
  - 統計タイル — 就寝/勤務/移動/商店街/RIO/累計収支
  - 12人カード — 行動絵文字、現在地、モード進捗、残高、本日収入/支出

## データ更新

スケジュール定義 (`experiments/virtual-human/schedules.py` 等) を変更したら：

```bash
./generate-schedules.sh
```

で `Resources/schedules.json` を再生成し、Xcode で再ビルド。

## 既知の単純化 (Python 側と同じ)

- 平日/週末の2パターンのみ。祝日・年末年始は未対応
- 山本（看護師）・井上（工場）は本デモでは常時夜勤
- 駅間補間は等時間。実所要時分は未反映
- 天気はバッジ表示せず（Python 側で時間変動を切ったため）

## 拡張案

1. **HealthKit 連携** — 自分（ユーザ）を13人目として加え、実歩数で位置を更新
2. **WidgetKit** — ロック画面に「今 RIO に居る人数」「就寝中」を表示
3. **Live Activity** — 営業時間中の RIO 来店人数をダイナミックアイランドに常駐
4. **Push 通知** — 「商店街に3人以上いる」などの閾値で発火
5. **MapKit 経路案内** — 通勤路を `MKDirections` で実路線に置換
