import SwiftUI

struct HeaderView: View {
    @EnvironmentObject var time: TimeEngine

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .center) {
                VStack(alignment: .leading, spacing: 0) {
                    Text("霜降銀座コホート 監視ステーション")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(.secondary)
                    Text("N=12 / 半径15km")
                        .font(.system(size: 9))
                        .foregroundStyle(.tertiary)
                }
                Spacer()
                if !time.liveMode {
                    Button(action: { time.enterLive() }) {
                        Text("LIVE に戻る")
                            .font(.system(size: 11, weight: .bold))
                            .padding(.horizontal, 10)
                            .padding(.vertical, 4)
                            .background(Color.green)
                            .foregroundColor(.black)
                            .clipShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(time.clockString)
                    .font(.system(size: 26, weight: .heavy, design: .monospaced))
                    .foregroundColor(.orange)
                Text("JST")
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
                Text(time.dateString)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                Text("(\(time.weekdayJP))")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(time.isWeekend ? .pink : .secondary)
                Spacer()
            }
            if !time.liveMode {
                Text("⏪ 過去の状態を表示中")
                    .font(.system(size: 10))
                    .foregroundColor(.yellow)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .shadow(color: .black.opacity(0.35), radius: 6, y: 2)
    }
}
