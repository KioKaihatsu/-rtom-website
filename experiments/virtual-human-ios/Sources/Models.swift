import Foundation
import CoreLocation

/// Root payload bundled as schedules.json.
struct Payload: Codable {
    let origin: LatLng
    let rio: LatLng
    let pois: [POI]
    let personas: [PersonaData]
}

struct LatLng: Codable, Hashable {
    let lat: Double
    let lng: Double
    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: lat, longitude: lng)
    }
}

struct POI: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let lat: Double
    let lng: Double
    let kind: String

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: lat, longitude: lng)
    }
}

struct Workplace: Codable, Hashable {
    let id: String
    let name: String
    let lat: Double
    let lng: Double
}

struct PersonaData: Codable, Identifiable, Hashable {
    let id: Int
    let name: String
    let color: String
    let age: Int
    let gender: String
    let occupation: String
    let incomeJpyYear: Int
    let hourlyWageJpy: Int
    let homeName: String
    let homeLat: Double
    let homeLng: Double
    let kmFromShimofuri: Double
    let workplace: Workplace?
    let initialBalanceJpy: Int
    let scheduleWeekday: [Segment]
    let scheduleWeekend: [Segment]

    func schedule(weekend: Bool) -> [Segment] {
        weekend ? scheduleWeekend : scheduleWeekday
    }
}

/// Minified to match Python output: s/e/act/mode/place/wp/cost/wage/tp.
struct Segment: Codable, Identifiable, Hashable {
    let s: Int
    let e: Int
    let act: String
    let mode: String
    let place: String
    let wp: [[Double]]
    let cost: Int
    let wage: Int
    let tp: Touchpoint?

    var id: String { "\(s)-\(e)-\(act)" }
    var startMin: Int { s }
    var endMin: Int { e }
    var duration: Int { max(1, e - s) }
}

struct Touchpoint: Codable, Hashable {
    let channel: String?
    let brand: String?
}
