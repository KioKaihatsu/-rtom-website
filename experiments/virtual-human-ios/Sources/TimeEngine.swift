import Foundation
import SwiftUI

/// Drives the UI clock. Always reports Asia/Tokyo wall time. Updates every
/// 0.5s so movement looks smooth without burning battery.
@MainActor
final class TimeEngine: ObservableObject {
    @Published var liveMinuteOfDay: Double = 0
    @Published var scrubMinuteOfDay: Double = 0
    @Published var liveMode: Bool = true
    @Published var clockString: String = "--:--:--"
    @Published var dateString: String = ""
    @Published var weekdayJP: String = ""
    @Published var isWeekend: Bool = false

    private var timer: Timer?
    private static let jst = TimeZone(identifier: "Asia/Tokyo")!

    init() {
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick() }
        }
        tick()
    }

    /// Minute the UI is currently rendering (live or scrubbed).
    var displayMinute: Double {
        liveMode ? liveMinuteOfDay : min(scrubMinuteOfDay, liveMinuteOfDay)
    }

    func enterLive() {
        liveMode = true
        scrubMinuteOfDay = liveMinuteOfDay
    }

    func setScrub(_ value: Double) {
        liveMode = false
        scrubMinuteOfDay = min(value, liveMinuteOfDay)
    }

    private func tick() {
        let now = Date()
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = Self.jst
        let comps = cal.dateComponents(
            [.year, .month, .day, .hour, .minute, .second, .weekday], from: now)
        let h = comps.hour ?? 0, m = comps.minute ?? 0, s = comps.second ?? 0
        let mod = Double(h * 60 + m) + Double(s) / 60.0
        liveMinuteOfDay = mod
        if liveMode { scrubMinuteOfDay = mod }

        let clockFmt = DateFormatter()
        clockFmt.timeZone = Self.jst
        clockFmt.dateFormat = "HH:mm:ss"
        clockString = clockFmt.string(from: now)

        let dateFmt = DateFormatter()
        dateFmt.timeZone = Self.jst
        dateFmt.dateFormat = "yyyy-MM-dd"
        dateString = dateFmt.string(from: now)

        // Calendar.weekday: 1=Sunday ... 7=Saturday
        let w = comps.weekday ?? 1
        weekdayJP = ["日", "月", "火", "水", "木", "金", "土"][w - 1]
        isWeekend = (w == 1 || w == 7)
    }
}
