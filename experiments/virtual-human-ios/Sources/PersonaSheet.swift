import SwiftUI

struct PersonaSheet: View {
    let payload: Payload
    @EnvironmentObject var time: TimeEngine

    var body: some View {
        VStack(spacing: 0) {
            ScrubBar()
                .padding(.horizontal, 16)
                .padding(.top, 6)
            StatsBar(payload: payload, minute: time.displayMinute, weekend: time.isWeekend)
                .padding(.horizontal, 16)
                .padding(.top, 8)
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(payload.personas) { p in
                        PersonaCardView(
                            persona: p,
                            minute: time.displayMinute,
                            weekend: time.isWeekend
                        )
                        Divider().padding(.leading, 38)
                    }
                }
                .padding(.top, 8)
            }
        }
        .background(Color.black.opacity(0.001))  // ensures hit-test
    }
}

private struct ScrubBar: View {
    @EnvironmentObject var time: TimeEngine
    @State private var sliderValue: Double = 0

    var body: some View {
        HStack(spacing: 10) {
            Text("過去を見る")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
            Slider(
                value: Binding(
                    get: { time.liveMode ? time.liveMinuteOfDay : time.scrubMinuteOfDay },
                    set: { time.setScrub($0) }
                ),
                in: 0...max(1, time.liveMinuteOfDay)
            )
            .tint(.orange)
            if !time.liveMode {
                Button("LIVE") { time.enterLive() }
                    .font(.system(size: 11, weight: .bold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(Color.green)
                    .foregroundColor(.black)
                    .clipShape(Capsule())
                    .buttonStyle(.plain)
            }
        }
    }
}
