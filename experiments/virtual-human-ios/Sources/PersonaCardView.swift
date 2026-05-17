import SwiftUI

struct PersonaCardView: View {
    let persona: PersonaData
    let minute: Double
    let weekend: Bool

    var body: some View {
        let segs = persona.schedule(weekend: weekend)
        let seg = persona.segment(at: minute, segments: segs)
        let cum = persona.cumulative(at: minute, segments: segs)
        let balance = persona.initialBalanceJpy + cum.earned - cum.spent
        let sleeping = seg.act == "sleep"
        let moving = seg.mode != "stay"
        let atRIO = seg.tp?.brand == "Riverbed in Otherworld"
        let atShot = seg.tp?.channel == "霜降銀座" && !atRIO

        HStack(alignment: .top, spacing: 12) {
            // Color dot
            ZStack {
                Circle()
                    .fill(Color(hex: persona.color))
                    .frame(width: 14, height: 14)
                if moving {
                    Circle()
                        .stroke(Color(hex: persona.color), lineWidth: 1)
                        .frame(width: 22, height: 22)
                }
            }
            .padding(.top, 4)

            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(persona.name)
                        .font(.system(size: 14, weight: .bold))
                    Text("(\(persona.age))")
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                    Spacer()
                    if atRIO {
                        Text("★ RIO")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundColor(.black)
                            .padding(.horizontal, 6).padding(.vertical, 2)
                            .background(.orange).clipShape(Capsule())
                    } else if atShot {
                        Text("商店街")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundColor(.black)
                            .padding(.horizontal, 6).padding(.vertical, 2)
                            .background(.yellow).clipShape(Capsule())
                    }
                }

                Text("\(persona.occupation) / \(persona.homeName) "
                     + "(\(String(format: "%.1f", persona.kmFromShimofuri))km)")
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)

                Text(Activities.label(seg.act))
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(.orange)

                HStack(spacing: 6) {
                    Text("@ \(seg.place)")
                        .font(.system(size: 11))
                        .foregroundStyle(.primary)
                        .lineLimit(1)
                    if moving {
                        Text("·")
                            .foregroundStyle(.secondary)
                        Text(Activities.modeLabel(seg.mode)
                             + " \(Int(seg.progress(at: minute) * 100))%")
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)
                    }
                }

                HStack(spacing: 14) {
                    Label {
                        Text("¥\(balance.formatted(.number.grouping(.automatic)))")
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    } icon: {
                        Image(systemName: "yensign.circle")
                            .font(.system(size: 11))
                    }
                    .foregroundStyle(.primary)
                    Spacer()
                    Text("+¥\(cum.earned.formatted(.number.grouping(.automatic)))")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.green)
                    Text("−¥\(cum.spent.formatted(.number.grouping(.automatic)))")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.pink)
                }
                .padding(.top, 2)
            }
            .opacity(sleeping ? 0.55 : 1.0)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(rowBackground(atRIO: atRIO, atShot: atShot))
    }

    private func rowBackground(atRIO: Bool, atShot: Bool) -> some View {
        Group {
            if atRIO { Color.orange.opacity(0.18) }
            else if atShot { Color.yellow.opacity(0.08) }
            else { Color.clear }
        }
    }
}
