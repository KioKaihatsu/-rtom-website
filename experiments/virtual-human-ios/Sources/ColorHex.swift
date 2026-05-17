import SwiftUI

extension Color {
    /// Parse "#rrggbb" or "rrggbb" into a Color. Falls back to gray on bad input.
    init(hex: String) {
        var s = hex.uppercased()
        if s.hasPrefix("#") { s.removeFirst() }
        guard s.count == 6, let v = Int(s, radix: 16) else {
            self = .gray
            return
        }
        self.init(
            red:   Double((v >> 16) & 0xFF) / 255.0,
            green: Double((v >>  8) & 0xFF) / 255.0,
            blue:  Double( v        & 0xFF) / 255.0
        )
    }
}
