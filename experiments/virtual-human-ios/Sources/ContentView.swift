import SwiftUI

struct ContentView: View {
    @EnvironmentObject var time: TimeEngine
    private let payload: Payload = PayloadLoader.load()
    @State private var sheetHeight: PresentationDetent = .fraction(0.42)

    var body: some View {
        ZStack(alignment: .top) {
            MapView(
                payload: payload,
                minute: time.displayMinute,
                weekend: time.isWeekend
            )
            .ignoresSafeArea()

            HeaderView()
                .padding(.horizontal, 12)
                .padding(.top, 8)
        }
        .sheet(isPresented: .constant(true)) {
            PersonaSheet(payload: payload)
                .presentationDetents(
                    [.fraction(0.16), .fraction(0.42), .large],
                    selection: $sheetHeight
                )
                .presentationBackgroundInteraction(.enabled)
                .presentationDragIndicator(.visible)
                .interactiveDismissDisabled()
        }
    }
}
