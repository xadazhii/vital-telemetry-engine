import SwiftUI
import HealthKit
import CoreLocation
import Combine

extension Color {
    static let appBg        = Color(r: 7,   g: 7,   b: 16)
    static let cardBg       = Color(r: 15,  g: 15,  b: 26)
    static let cardBorder   = Color(r: 30,  g: 30,  b: 48)
    static let accent       = Color(r: 230, g: 59,  b: 111)
    static let accentGreen  = Color(r: 16,  g: 217, b: 160)
    static let accentBlue   = Color(r: 56,  g: 189, b: 248)
    static let accentPurple = Color(r: 167, g: 139, b: 250)
    static let textMain     = Color(r: 240, g: 240, b: 255)
    static let textMuted    = Color(r: 107, g: 107, b: 138)

    init(r: Double, g: Double, b: Double) {
        self.init(red: r / 255, green: g / 255, blue: b / 255)
    }
}

struct CardView<Content: View>: View {
    let content: Content
    init(@ViewBuilder content: () -> Content) { self.content = content() }
    var body: some View {
        content
            .padding(16)
            .background(Color.cardBg)
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.cardBorder, lineWidth: 1))
            .cornerRadius(16)
    }
}

struct MetricTile: View {
    let label: String
    let value: String
    let unit: String
    let color: Color
    var badge: String? = nil
    var badgeColor: Color = .accentGreen

    var body: some View {
        CardView {
            VStack(alignment: .leading, spacing: 6) {
                Text(label)
                    .font(.system(size: 10, weight: .semibold))
                    .tracking(1.2)
                    .foregroundColor(.textMuted)
                    .textCase(.uppercase)

                HStack(alignment: .firstTextBaseline, spacing: 3) {
                    Text(value)
                        .font(.system(size: 28, weight: .black, design: .rounded))
                        .foregroundColor(color)
                    Text(unit)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(.textMuted)
                }

                if let badge = badge {
                    Text(badge)
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(badgeColor)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(badgeColor.opacity(0.15))
                        .cornerRadius(99)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct ActionButton: View {
    let title: String
    let icon: String
    let color: Color
    var isLoading: Bool = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if isLoading {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(0.75)
                } else {
                    Image(systemName: icon)
                        .font(.system(size: 14, weight: .semibold))
                }
                Text(isLoading ? "Working..." : title)
                    .font(.system(size: 15, weight: .bold))
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 11, weight: .bold))
                    .opacity(0.5)
            }
            .foregroundColor(.white)
            .padding(.horizontal, 18)
            .padding(.vertical, 16)
            .background(isLoading ? Color.cardBorder : color)
            .cornerRadius(14)
        }
        .disabled(isLoading)
    }
}

struct DarkField: View {
    let placeholder: String
    @Binding var text: String
    var keyboard: UIKeyboardType = .default

    var body: some View {
        TextField(placeholder, text: $text)
            .font(.system(size: 14))
            .foregroundColor(.textMain)
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .background(Color.cardBg)
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.cardBorder, lineWidth: 1))
            .cornerRadius(10)
            .keyboardType(keyboard)
            .autocapitalization(.none)
            .disableAutocorrection(true)
    }
}

class PhoneConnector: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published var lastSystolic: Double = 0.0
    @Published var lastDiastolic: Double = 0.0
    @Published var lastHeartRate: Double = 0.0
    @Published var lastSpo2: Double = 0.0
    @Published var lastHRV: Double = 0.0
    @Published var airQualityIndex: Int = 0
    @Published var airQualityLabel: String = ""
    @Published var pm25: Double = 0.0
    @Published var userAge: Int = 0
    @Published var userHeight: Double = 0.0
    @Published var userWeight: Double = 0.0
    @Published var userName: String = UserDefaults.standard.string(forKey: "userName") ?? ""

    @Published var serverStatus: String = "Idle"
    @Published var statusOK: Bool = false
    @Published var serverIP: String = "172.20.10.6"
    @Published var isImporting: Bool = false
    @Published var importProgress: String = ""
    @Published var lastSyncTime: Date? = nil

    private let healthStore = HKHealthStore()
    private var observers: [HKObserverQuery] = []
    private var syncWorkItem: DispatchWorkItem?
    private let locationManager = CLLocationManager()

    override init() {
        super.init()
        locationManager.delegate = self
        locationManager.requestWhenInUseAuthorization()
        requestHealthKitAuthorization()
    }

    func locationManager(_ manager: CLLocationManager, didChangeAuthorization status: CLAuthorizationStatus) {
        if status == .authorizedWhenInUse || status == .authorizedAlways {
            manager.requestLocation()
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.first else { return }
        fetchAirQuality(lat: loc.coordinate.latitude, lon: loc.coordinate.longitude)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {}

    func refreshAirQuality() { locationManager.requestLocation() }

    private func fetchAirQuality(lat: Double, lon: Double) {
        guard let url = URL(string: "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=\(lat)&longitude=\(lon)&current=european_aqi,pm2_5,pm10") else { return }
        URLSession.shared.dataTask(with: url) { data, _, _ in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let current = json["current"] as? [String: Any] else { return }
            let aqi  = current["european_aqi"] as? Int ?? 0
            let pm25 = current["pm2_5"] as? Double ?? 0.0
            DispatchQueue.main.async {
                self.airQualityIndex = aqi
                self.pm25            = pm25
                self.airQualityLabel = self.aqiLabel(aqi)
            }
        }.resume()
    }

    private func aqiLabel(_ aqi: Int) -> String {
        switch aqi {
        case 0..<20:  return "Good"
        case 20..<40: return "Fair"
        case 40..<60: return "Moderate"
        case 60..<80: return "Poor"
        case 80..<100:return "Very Poor"
        default:       return "Hazardous"
        }
    }

    var aqiColor: Color {
        switch airQualityIndex {
        case 0..<20:  return .accentGreen
        case 20..<40: return Color(r: 154, g: 205, b: 50)
        case 40..<60: return Color(r: 249, g: 115, b: 22)
        case 60..<80: return .accent
        default:       return Color(r: 167, g: 139, b: 250)
        }
    }

    var bmi: Double {
        guard userHeight > 0, userWeight > 0 else { return 0 }
        let h = userHeight / 100
        return userWeight / (h * h)
    }

    var bmiLabel: String {
        switch bmi {
        case ..<18.5: return "Underweight"
        case ..<25:   return "Normal"
        case ..<30:   return "Overweight"
        default:      return "Obese"
        }
    }

    var bmiColor: Color {
        switch bmi {
        case ..<18.5: return .accentBlue
        case ..<25:   return .accentGreen
        case ..<30:   return Color(r: 249, g: 115, b: 22)
        default:      return .accent
        }
    }

    func requestHealthKitAuthorization() {
        guard HKHealthStore.isHealthDataAvailable() else {
            serverStatus = "HealthKit unavailable"; return
        }
        guard let sys  = HKQuantityType.quantityType(forIdentifier: .bloodPressureSystolic),
              let dia  = HKQuantityType.quantityType(forIdentifier: .bloodPressureDiastolic),
              let hr   = HKQuantityType.quantityType(forIdentifier: .heartRate),
              let hrv  = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN),
              let spo2 = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation),
              let h    = HKQuantityType.quantityType(forIdentifier: .height),
              let w    = HKQuantityType.quantityType(forIdentifier: .bodyMass),
              let dob  = HKObjectType.characteristicType(forIdentifier: .dateOfBirth) else { return }

        healthStore.requestAuthorization(toShare: nil, read: [sys, dia, hr, hrv, spo2, h, w, dob]) { ok, _ in
            DispatchQueue.main.async {
                if ok {
                    self.fetchAllHealthData()
                    self.setupObservers()
                } else {
                    self.serverStatus = "HealthKit not authorized"
                }
            }
        }
    }

    private func setupObservers() {
        let types: [HKSampleType] = [
            HKQuantityType.quantityType(forIdentifier: .heartRate)!,
            HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN)!,
            HKQuantityType.quantityType(forIdentifier: .oxygenSaturation)!,
            HKQuantityType.quantityType(forIdentifier: .bloodPressureSystolic)!,
            HKQuantityType.quantityType(forIdentifier: .bodyMass)!,
            HKQuantityType.quantityType(forIdentifier: .height)!,
        ]

        for type in types {
            healthStore.enableBackgroundDelivery(for: type, frequency: .immediate) { _, _ in }

            let query = HKObserverQuery(sampleType: type, predicate: nil) { [weak self] _, completion, error in
                guard let self = self, error == nil else { completion(); return }
                self.scheduleDebouncedSync()
                completion()
            }
            observers.append(query)
            healthStore.execute(query)
        }
    }

    private func scheduleDebouncedSync() {
        syncWorkItem?.cancel()
        let work = DispatchWorkItem { [weak self] in
            self?.fetchAllHealthData()
        }
        syncWorkItem = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 2, execute: work)
    }

    func fetchAllHealthData() {
        fetchAge()
        fetchLatestHeight()
        fetchLatestWeight()
        fetchLatestSpO2()
        fetchLatestHRV()
        fetchLatestBloodPressureAndHeartRate()
    }

    private func fetchLatestSpO2() {
        guard let t = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation) else { return }
        let q = HKSampleQuery(sampleType: t, predicate: nil, limit: 1,
                              sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { _, r, _ in
            if let s = r?.first as? HKQuantitySample {
                let pct = s.quantity.doubleValue(for: HKUnit.percent()) * 100
                DispatchQueue.main.async { self.lastSpo2 = pct }
            }
        }
        healthStore.execute(q)
    }

    private func fetchLatestHRV() {
        guard let t = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN) else { return }
        let q = HKSampleQuery(sampleType: t, predicate: nil, limit: 1,
                              sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { _, r, _ in
            if let s = r?.first as? HKQuantitySample {
                let hrv = s.quantity.doubleValue(for: HKUnit.secondUnit(with: .milli))
                DispatchQueue.main.async { self.lastHRV = hrv }
            }
        }
        healthStore.execute(q)
    }

    private func fetchAge() {
        let cal = Calendar.current
        if let c = try? healthStore.dateOfBirthComponents(), let y = c.year {
            DispatchQueue.main.async { self.userAge = cal.component(.year, from: Date()) - y }
        }
    }

    private func fetchLatestHeight() {
        guard let t = HKQuantityType.quantityType(forIdentifier: .height) else { return }
        let q = HKSampleQuery(sampleType: t, predicate: nil, limit: 1,
                              sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { _, r, _ in
            if let s = r?.first as? HKQuantitySample {
                DispatchQueue.main.async { self.userHeight = s.quantity.doubleValue(for: .meterUnit(with: .centi)) }
            }
        }
        healthStore.execute(q)
    }

    private func fetchLatestWeight() {
        guard let t = HKQuantityType.quantityType(forIdentifier: .bodyMass) else { return }
        let q = HKSampleQuery(sampleType: t, predicate: nil, limit: 1,
                              sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { _, r, _ in
            if let s = r?.first as? HKQuantitySample {
                DispatchQueue.main.async { self.userWeight = s.quantity.doubleValue(for: .gramUnit(with: .kilo)) }
            }
        }
        healthStore.execute(q)
    }

    private func fetchLatestBloodPressureAndHeartRate() {
        guard let bpType = HKCorrelationType.correlationType(forIdentifier: .bloodPressure),
              let sysT   = HKQuantityType.quantityType(forIdentifier: .bloodPressureSystolic),
              let diaT   = HKQuantityType.quantityType(forIdentifier: .bloodPressureDiastolic),
              let hrT    = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return }

        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)

        let bpQ = HKSampleQuery(sampleType: bpType, predicate: nil, limit: 1, sortDescriptors: [sort]) { _, res, _ in
            guard let corr = (res as? [HKCorrelation])?.first else { return }
            let sys = (corr.objects(for: sysT).first as? HKQuantitySample)?.quantity.doubleValue(for: .millimeterOfMercury()) ?? 0
            let dia = (corr.objects(for: diaT).first as? HKQuantitySample)?.quantity.doubleValue(for: .millimeterOfMercury()) ?? 0

            let hrQ = HKSampleQuery(sampleType: hrT, predicate: nil, limit: 1, sortDescriptors: [sort]) { _, hrRes, _ in
                let hr = (hrRes?.first as? HKQuantitySample)?.quantity.doubleValue(for: .count().unitDivided(by: .minute())) ?? 0
                DispatchQueue.main.async {
                    self.lastSystolic = sys; self.lastDiastolic = dia; self.lastHeartRate = hr
                    self.sendAllDataToServer()
                }
            }
            self.healthStore.execute(hrQ)
        }
        healthStore.execute(bpQ)
    }

    func importHeartRateHistory(days: Int = 7) {
        guard let hrType = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return }
        let start = Calendar.current.date(byAdding: .day, value: -days, to: Date())!
        let pred  = HKQuery.predicateForSamples(withStart: start, end: Date(), options: .strictStartDate)
        let sort  = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)

        DispatchQueue.main.async { self.isImporting = true; self.importProgress = "Reading health history..." }

        let q = HKSampleQuery(sampleType: hrType, predicate: pred, limit: HKObjectQueryNoLimit, sortDescriptors: [sort]) { [weak self] _, res, err in
            guard let self else { return }
            if err != nil {
                DispatchQueue.main.async { self.isImporting = false; self.importProgress = "Read error" }
                return
            }
            let fmt = ISO8601DateFormatter()
            fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            let unit = HKUnit.count().unitDivided(by: .minute())
            let readings = (res as? [HKQuantitySample] ?? []).map {
                ["heart_rate": $0.quantity.doubleValue(for: unit), "timestamp": fmt.string(from: $0.startDate)]
            }
            DispatchQueue.main.async { self.importProgress = "Sending \(readings.count) records..." }

            guard let url = URL(string: "http://\(self.serverIP):8000/telemetry/history-import") else {
                DispatchQueue.main.async { self.isImporting = false; self.importProgress = "Invalid IP" }
                return
            }
            let name = self.userName.trimmingCharacters(in: .whitespaces).isEmpty ? "Apple Watch User" : self.userName.trimmingCharacters(in: .whitespaces)
            var req = URLRequest(url: url)
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.timeoutInterval = 60
            req.httpBody = try? JSONSerialization.data(withJSONObject: ["name": name, "readings": readings])

            URLSession.shared.dataTask(with: req) { _, resp, err in
                DispatchQueue.main.async {
                    self.isImporting = false
                    if err != nil { self.importProgress = "Network error" }
                    else if (resp as? HTTPURLResponse)?.statusCode == 200 {
                        self.importProgress = "✅ \(readings.count) records imported"
                        self.statusOK = true
                        self.serverStatus = "History synced"
                    } else { self.importProgress = "Server error" }
                }
            }.resume()
        }
        healthStore.execute(q)
    }

    func sendAllDataToServer() {
        guard let url = URL(string: "http://\(serverIP):8000/telemetry/apple-health") else {
            serverStatus = "Invalid IP"; return
        }
        let name = userName.trimmingCharacters(in: .whitespaces).isEmpty ? "Apple Watch User" : userName.trimmingCharacters(in: .whitespaces)
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        var payload: [String: Any] = [
            "name": name, "age": userAge, "height": userHeight, "weight": userWeight,
            "systolic": lastSystolic, "diastolic": lastDiastolic, "heart_rate": lastHeartRate
        ]
        if lastSpo2 > 0 { payload["spo2"] = lastSpo2 }
        if lastHRV > 0 { payload["device_hrv"] = lastHRV }
        if airQualityIndex > 0 {
            payload["aqi"] = airQualityIndex
            payload["pm25"] = pm25
        }
        req.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        URLSession.shared.dataTask(with: req) { _, resp, err in
            DispatchQueue.main.async {
                if err != nil {
                    self.serverStatus = "Connection error"; self.statusOK = false
                } else if (resp as? HTTPURLResponse)?.statusCode == 200 {
                    self.lastSyncTime = Date()
                    self.statusOK = true
                    let t = DateFormatter.localizedString(from: Date(), dateStyle: .none, timeStyle: .short)
                    self.serverStatus = "Auto-synced at \(t)"
                } else {
                    self.serverStatus = "Server error"; self.statusOK = false
                }
            }
        }.resume()
    }
}

struct CompactTile: View {
    let label: String
    let value: String
    let unit: String
    let color: Color
    let systemIcon: String

    var body: some View {
        CardView {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 5) {
                    Image(systemName: systemIcon)
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(color.opacity(0.8))
                    Text(label)
                        .font(.system(size: 10, weight: .semibold))
                        .tracking(0.8)
                        .foregroundColor(.textMuted)
                        .textCase(.uppercase)
                }
                HStack(alignment: .firstTextBaseline, spacing: 2) {
                    Text(value)
                        .font(.system(size: 22, weight: .bold, design: .rounded))
                        .foregroundColor(color)
                    Text(unit)
                        .font(.system(size: 10, weight: .medium))
                        .foregroundColor(.textMuted)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct ProfileMini: View {
    let label: String
    let value: String
    var body: some View {
        VStack(spacing: 1) {
            Text(value)
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(.textMain)
            Text(label)
                .font(.system(size: 9, weight: .medium))
                .foregroundColor(.textMuted)
                .textCase(.uppercase)
        }
    }
}

struct ContentView: View {
    @StateObject private var connector = PhoneConnector()
    @State private var heartPulse = false

    var body: some View {
        ZStack {
            Color.appBg.ignoresSafeArea()

            ScrollView(showsIndicators: false) {
                VStack(spacing: 14) {

                    HStack {
                        VStack(alignment: .leading, spacing: 1) {
                            Text("Cardio Live")
                                .font(.system(size: 18, weight: .bold, design: .rounded))
                                .foregroundColor(.textMain)
                            Text("Health Bridge")
                                .font(.system(size: 11))
                                .foregroundColor(.textMuted)
                        }
                        Spacer()
                        LiveBadge(ok: connector.statusOK)
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 16)

                    CardView {
                        HStack(alignment: .center) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("HEART RATE")
                                    .font(.system(size: 10, weight: .semibold))
                                    .tracking(1.5)
                                    .foregroundColor(.textMuted)

                                HStack(alignment: .firstTextBaseline, spacing: 4) {
                                    Text(connector.lastHeartRate > 0 ? "\(Int(connector.lastHeartRate))" : "--")
                                        .font(.system(size: 56, weight: .black, design: .rounded))
                                        .foregroundColor(.accent)
                                        .scaleEffect(heartPulse ? 1.04 : 1.0)
                                        .animation(.easeInOut(duration: 0.4).repeatForever(autoreverses: true), value: heartPulse)
                                    Text("BPM")
                                        .font(.system(size: 18, weight: .semibold))
                                        .foregroundColor(.textMuted)
                                        .padding(.bottom, 4)
                                }

                                if let t = connector.lastSyncTime {
                                    Text("Updated \(DateFormatter.localizedString(from: t, dateStyle: .none, timeStyle: .short))")
                                        .font(.system(size: 11))
                                        .foregroundColor(.textMuted)
                                } else {
                                    Text(connector.serverStatus)
                                        .font(.system(size: 11))
                                        .foregroundColor(connector.statusOK ? .accentGreen : .textMuted)
                                        .lineLimit(1)
                                }
                            }
                            Spacer()
                            ZStack {
                                Circle()
                                    .stroke(Color.accent.opacity(0.12), lineWidth: 3)
                                    .frame(width: 64, height: 64)
                                Circle()
                                    .stroke(Color.accent.opacity(0.35), lineWidth: 3)
                                    .frame(width: 64, height: 64)
                                    .scaleEffect(heartPulse ? 1.15 : 1.0)
                                    .opacity(heartPulse ? 0 : 0.6)
                                    .animation(.easeOut(duration: 0.8).repeatForever(autoreverses: false), value: heartPulse)
                                Image(systemName: "waveform.path.ecg")
                                    .font(.system(size: 22, weight: .medium))
                                    .foregroundColor(.accent.opacity(0.7))
                            }
                        }
                    }
                    .padding(.horizontal, 20)
                    .onAppear { heartPulse = true }

                    HStack(spacing: 10) {
                        CompactTile(
                            label: "Blood Pressure",
                            value: connector.lastSystolic > 0 ? "\(Int(connector.lastSystolic))/\(Int(connector.lastDiastolic))" : "--",
                            unit: "mmHg",
                            color: .accentBlue,
                            systemIcon: "heart.text.square"
                        )
                        CompactTile(
                            label: "HRV",
                            value: connector.lastHRV > 0 ? String(format: "%.0f", connector.lastHRV) : "--",
                            unit: "ms",
                            color: .accentPurple,
                            systemIcon: "waveform"
                        )
                        CompactTile(
                            label: "Air",
                            value: connector.airQualityIndex > 0 ? "\(connector.airQualityIndex)" : "--",
                            unit: "AQI",
                            color: connector.aqiColor,
                            systemIcon: "wind"
                        )
                    }
                    .padding(.horizontal, 20)

                    if connector.userAge > 0 || connector.userHeight > 0 {
                        CardView {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(connector.userName.isEmpty ? "Patient" : connector.userName)
                                        .font(.system(size: 14, weight: .bold))
                                        .foregroundColor(.textMain)
                                    Text("BMI \(connector.bmi > 0 ? String(format:"%.1f", connector.bmi) : "--") · \(connector.bmiLabel)")
                                        .font(.system(size: 11))
                                        .foregroundColor(connector.bmiColor)
                                }
                                Spacer()
                                HStack(spacing: 16) {
                                    ProfileMini(label: "Age",  value: connector.userAge > 0 ? "\(connector.userAge)y" : "--")
                                    ProfileMini(label: "Ht",   value: connector.userHeight > 0 ? "\(Int(connector.userHeight))" : "--")
                                    ProfileMini(label: "Wt",   value: connector.userWeight > 0 ? "\(Int(connector.userWeight))" : "--")
                                }
                            }
                        }
                        .padding(.horizontal, 20)
                    }

                    VStack(spacing: 8) {
                        ActionButton(title: "Sync Now", icon: "arrow.up.heart.fill", color: .accent) {
                            connector.fetchAllHealthData()
                            connector.refreshAirQuality()
                        }
                        ActionButton(title: "Import 7-Day History", icon: "arrow.down.heart.fill", color: .accentPurple, isLoading: connector.isImporting) {
                            connector.importHeartRateHistory(days: 7)
                        }
                        if !connector.importProgress.isEmpty {
                            Text(connector.importProgress)
                                .font(.system(size: 11))
                                .foregroundColor(.accentPurple)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 4)
                        }
                    }
                    .padding(.horizontal, 20)

                    CardView {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Settings")
                                .font(.system(size: 10, weight: .semibold))
                                .tracking(1.2)
                                .foregroundColor(.textMuted)
                                .textCase(.uppercase)

                            HStack(spacing: 10) {
                                Text("Name")
                                    .font(.system(size: 12, weight: .medium))
                                    .foregroundColor(.textMuted)
                                    .frame(width: 44, alignment: .leading)
                                DarkField(placeholder: "Your name", text: $connector.userName)
                                    .onChange(of: connector.userName) {
                                        UserDefaults.standard.set($0, forKey: "userName")
                                    }
                            }
                            HStack(spacing: 10) {
                                Text("Server")
                                    .font(.system(size: 12, weight: .medium))
                                    .foregroundColor(.textMuted)
                                    .frame(width: 44, alignment: .leading)
                                DarkField(placeholder: "192.168.x.x", text: $connector.serverIP, keyboard: .numbersAndPunctuation)
                            }
                        }
                    }
                    .padding(.horizontal, 20)

                    StatusBar(message: connector.serverStatus, ok: connector.statusOK)
                        .padding(.horizontal, 20)
                        .padding(.bottom, 24)
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}

struct LiveBadge: View {
    let ok: Bool
    @State private var pulse = false

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(ok ? Color.accentGreen : Color.textMuted)
                .frame(width: 7, height: 7)
                .shadow(color: ok ? Color.accentGreen.opacity(0.8) : .clear, radius: pulse ? 5 : 2)
                .scaleEffect(pulse ? 1.2 : 1.0)
                .animation(.easeInOut(duration: 1.2).repeatForever(), value: pulse)
                .onAppear { pulse = true }
            Text(ok ? "LIVE" : "IDLE")
                .font(.system(size: 11, weight: .bold))
                .foregroundColor(ok ? .accentGreen : .textMuted)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background((ok ? Color.accentGreen : Color.textMuted).opacity(0.1))
        .overlay(RoundedRectangle(cornerRadius: 99).stroke((ok ? Color.accentGreen : Color.textMuted).opacity(0.25), lineWidth: 1))
        .cornerRadius(99)
    }
}

struct ProfileStat: View {
    let label: String
    let value: String
    var body: some View {
        VStack(spacing: 3) {
            Text(label)
                .font(.system(size: 9, weight: .semibold))
                .tracking(0.8)
                .foregroundColor(.textMuted)
                .textCase(.uppercase)
            Text(value)
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(.textMain)
        }
        .frame(maxWidth: .infinity)
    }
}

struct StatusBar: View {
    let message: String
    let ok: Bool
    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(ok ? Color.accentGreen : Color.textMuted)
                .frame(width: 6, height: 6)
            Text(message)
                .font(.system(size: 12))
                .foregroundColor(ok ? .accentGreen : .textMuted)
            Spacer()
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Color.cardBg)
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.cardBorder, lineWidth: 1))
        .cornerRadius(10)
    }
}

#Preview {
    ContentView()
}
