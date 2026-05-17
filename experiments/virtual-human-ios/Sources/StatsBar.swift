import SwiftUI

struct StatsBar: View {
    let payload: Payload
    let minute: Double
    let weekend: Bool

    var body: some View {
        let stats = computeStats()
        LazyVGrid(
            columns: [
                GridItem(.flexible(), spacing: 4),
                GridItem(.flexible(), spacing: 4),
                GridItem(.flexible(), spacing: 4),
            ],
            spacing: 6
        ) {
            tile("就寝中",  "\(stats.sleeping)人", .secondary)
            tile("勤務中",  "\(stats.working)人",  .green)
            tile("移動中",  "\(stats.moving)人",   .blue)
            tile("商店街",  "\(stats.shotengai)人", .yellow)
            tile("RIO来店", "\(stats.rio)人",     .orange)
            tile("累計収支",
                 (stats.earned - stats.spent >= 0 ? "+" : "")
                 + "¥\(stats.earned - stats.spent)",
                 .primary)
        }
        .padding(10)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private struct Stats {
        var sleeping = 0, working = 0, moving = 0
        var shotengai = 0, rio = 0
        var earned = 0, spent = 0
    }

    private func computeStats() -> Stats {
        var s = Stats()
        for p in payload.personas {
            let segs = p.schedule(weekend: weekend)
            let seg = p.segment(at: minute, segments: segs)
            if seg.act == "sleep" { s.sleeping += 1 }
            if Activities.isWorking(seg.act) { s.working += 1 }
            if seg.mode != "stay" { s.moving += 1 }
            if seg.tp?.channel == "霜降銀座" { s.shotengai += 1 }
            if seg.tp?.brand == "Riverbed in Otherworld" { s.rio += 1 }
            let cum = p.cumulative(at: minute, segments: segs)
            s.earned += cum.earned
            s.spent += cum.spent
        }
        return s
    }

    @ViewBuilder
    private func tile(_ label: String, _ value: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(label).font(.system(size: 10)).foregroundStyle(.secondary)
            Text(value)
                .font(.system(size: 14, weight: .bold, design: .rounded))
                .foregroundStyle(color)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
