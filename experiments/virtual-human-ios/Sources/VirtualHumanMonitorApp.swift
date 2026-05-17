import SwiftUI

@main
struct VirtualHumanMonitorApp: App {
    @StateObject private var time = TimeEngine()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(time)
                .preferredColorScheme(.dark)
        }
    }
}
