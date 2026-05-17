import Foundation

enum PayloadLoader {
    /// Load schedules.json from the app bundle. Fatal on failure — the JSON
    /// is a build-time artefact; missing means broken build.
    static func load() -> Payload {
        guard let url = Bundle.main.url(forResource: "schedules", withExtension: "json") else {
            fatalError("schedules.json not found in bundle. "
                       + "Re-run experiments/virtual-human-ios/generate-schedules.sh.")
        }
        let data: Data
        do { data = try Data(contentsOf: url) }
        catch { fatalError("Could not read schedules.json: \(error)") }

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        do { return try decoder.decode(Payload.self, from: data) }
        catch { fatalError("schedules.json malformed: \(error)") }
    }
}
