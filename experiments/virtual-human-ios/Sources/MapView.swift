import SwiftUI
import MapKit

struct MapView: View {
    let payload: Payload
    let minute: Double
    let weekend: Bool

    @State private var camera: MapCameraPosition = .region(
        MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: 35.7414, longitude: 139.7448),
            span:  MKCoordinateSpan(latitudeDelta: 0.18, longitudeDelta: 0.18)
        )
    )

    var body: some View {
        Map(position: $camera) {
            // Highlight ring around 霜降銀座
            MapCircle(
                center: payload.origin.coordinate,
                radius: 250
            )
            .foregroundStyle(Color.yellow.opacity(0.10))

            // Fixed POIs
            ForEach(payload.pois) { poi in
                Annotation(poi.name, coordinate: poi.coordinate, anchor: .center) {
                    POIDot(poi: poi)
                }
            }

            // Persona trails + markers
            ForEach(payload.personas) { p in
                let segs = p.schedule(weekend: weekend)
                let trail = p.trail(endingAt: minute, segments: segs)
                if trail.count >= 2 {
                    MapPolyline(coordinates: trail)
                        .stroke(
                            Color(hex: p.color).opacity(0.55),
                            style: StrokeStyle(lineWidth: 2.0, lineCap: .round, dash: [2, 4])
                        )
                }
            }
            ForEach(payload.personas) { p in
                let segs = p.schedule(weekend: weekend)
                let seg = p.segment(at: minute, segments: segs)
                let pos = seg.position(at: minute)
                Annotation(p.name, coordinate: pos, anchor: .center) {
                    PersonDot(
                        color: p.color,
                        moving: seg.mode != "stay",
                        sleeping: seg.act == "sleep",
                        atRIO: seg.tp?.brand == "Riverbed in Otherworld"
                    )
                }
            }
        }
        .mapStyle(.standard(elevation: .flat, pointsOfInterest: .excludingAll))
        .mapControls {
            MapCompass()
            MapScaleView()
        }
    }
}

private struct POIDot: View {
    let poi: POI

    var body: some View {
        let isRIO = poi.id == "rio"
        let isShot = poi.id == "shimofuri_ginza"
        ZStack {
            Circle()
                .fill(color.opacity(0.25))
                .frame(width: size + 8, height: size + 8)
            Circle()
                .stroke(color, lineWidth: 1.5)
                .frame(width: size, height: size)
            if isRIO {
                Text("★").font(.system(size: 11, weight: .bold)).foregroundColor(color)
            }
        }
        .help(poi.name)
    }

    private var color: Color {
        switch poi.id {
        case "rio": return .orange
        case "shimofuri_ginza": return .yellow
        default: return .gray
        }
    }
    private var size: CGFloat {
        switch poi.id {
        case "shimofuri_ginza": return 18
        case "rio": return 16
        default: return 10
        }
    }
}

private struct PersonDot: View {
    let color: String
    let moving: Bool
    let sleeping: Bool
    let atRIO: Bool
    @State private var animate = false

    var body: some View {
        let main = Color(hex: color)
        ZStack {
            if moving {
                Circle()
                    .stroke(main, lineWidth: 1.5)
                    .frame(width: 28, height: 28)
                    .scaleEffect(animate ? 1.0 : 0.5)
                    .opacity(animate ? 0 : 0.7)
                    .animation(
                        .easeOut(duration: 1.4).repeatForever(autoreverses: false),
                        value: animate
                    )
            }
            Circle()
                .fill(main)
                .frame(width: atRIO ? 18 : 14, height: atRIO ? 18 : 14)
                .overlay(
                    Circle().stroke(
                        atRIO ? Color.orange : Color.white,
                        lineWidth: atRIO ? 3 : 2
                    )
                )
                .opacity(sleeping ? 0.45 : 1.0)
        }
        .onAppear { animate = true }
    }
}
