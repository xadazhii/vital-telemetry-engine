import SwiftUI
import HealthKit
import WatchConnectivity
import Combine // Added to ensure @Published and ObservableObject compile perfectly

class WatchHeartRateManager: NSObject, ObservableObject, WCSessionDelegate, HKWorkoutSessionDelegate, HKLiveWorkoutBuilderDelegate {
    private var healthStore = HKHealthStore()
    private var workoutSession: HKWorkoutSession?
    private var builder: HKLiveWorkoutBuilder?
    
    @Published var currentHeartRate: Double = 0.0
    @Published var isMeasuring: Bool = false
    @Published var systemStatus: String = "Ready"
    
    override init() {
        super.init()
        if WCSession.isSupported() {
            let session = WCSession.default
            session.delegate = self
            session.activate()
        }
    }
    
    func requestAuthorization(completion: @escaping (Bool) -> Void) {
        guard HKHealthStore.isHealthDataAvailable() else {
            DispatchQueue.main.async {
                self.systemStatus = "Health Data Unavailable"
            }
            completion(false)
            return
        }
        
        let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate)!
        let typesToRead: Set = [heartRateType]
        let typesToShare: Set = [HKObjectType.workoutType()]
        
        healthStore.requestAuthorization(toShare: typesToShare, read: typesToRead) { success, error in
            DispatchQueue.main.async {
                if success {
                    self.systemStatus = "Authorized"
                    completion(true)
                } else {
                    if let error = error {
                        self.systemStatus = "Auth Error: \(error.localizedDescription)"
                    } else {
                        self.systemStatus = "Not Authorized"
                    }
                    completion(false)
                }
            }
        }
    }
    
    func startMeasurement() {
        requestAuthorization { [weak self] authorized in
            guard let self = self else { return }
            guard authorized else {
                DispatchQueue.main.async {
                    self.systemStatus = "Start Error: Not authorized"
                }
                return
            }
            
            let configuration = HKWorkoutConfiguration()
            configuration.activityType = .other
            configuration.locationType = .unknown
            
            do {
                let session = try HKWorkoutSession(healthStore: self.healthStore, configuration: configuration)
                let sessionBuilder = session.associatedWorkoutBuilder()
                
                self.workoutSession = session
                self.builder = sessionBuilder
                
                session.delegate = self
                sessionBuilder.delegate = self
                
                sessionBuilder.dataSource = HKLiveWorkoutDataSource(healthStore: self.healthStore, workoutConfiguration: configuration)
                
                let startDate = Date()
                session.startActivity(with: startDate)
                sessionBuilder.beginCollection(withStart: startDate) { success, error in
                    DispatchQueue.main.async {
                        if success {
                            self.isMeasuring = true
                            self.systemStatus = "Measuring..."
                        } else if let error = error {
                            self.systemStatus = "Start Error: \(error.localizedDescription)"
                        }
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    self.systemStatus = "Session initialization failed"
                }
            }
        }
    }
    
    func stopMeasurement() {
        workoutSession?.end()
        builder?.endCollection(withEnd: Date()) { success, error in
            DispatchQueue.main.async {
                self.isMeasuring = false
                self.currentHeartRate = 0.0
                self.systemStatus = "Stopped"
            }
        }
    }
    
    // WCSessionDelegate methods
    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        DispatchQueue.main.async {
            if let error = error {
                print("WCSession activation failed on watch: \(error.localizedDescription)")
            } else {
                print("WCSession activated on watch with state: \(activationState.rawValue)")
            }
        }
    }
    
    func sendToPhone(heartRate: Double) {
        if WCSession.default.isReachable {
            WCSession.default.sendMessage(["heartRate": heartRate], replyHandler: nil) { error in
                print("Failed to send telemetry to iPhone: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self.systemStatus = "Send Error: \(error.localizedDescription)"
                }
            }
        } else {
            print("iPhone is not reachable over WCSession")
            DispatchQueue.main.async {
                self.systemStatus = "Phone Unreachable"
            }
        }
    }
    
    // HKWorkoutSessionDelegate methods
    func workoutSession(_ workoutSession: HKWorkoutSession, didChangeTo toState: HKWorkoutSessionState, from fromState: HKWorkoutSessionState, date: Date) {}
    func workoutSession(_ workoutSession: HKWorkoutSession, didFailWithError error: Error) {}
    
    // HKLiveWorkoutBuilderDelegate methods
    func workoutBuilder(_ workoutBuilder: HKLiveWorkoutBuilder, didCollectDataOf types: Set<HKSampleType>) {
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return }
        
        if types.contains(heartRateType) {
            let statistics = workoutBuilder.statistics(for: heartRateType)
            if let quantity = statistics?.mostRecentQuantity() {
                let unit = HKUnit.count().unitDivided(by: HKUnit.minute())
                let value = quantity.doubleValue(for: unit)
                
                DispatchQueue.main.async {
                    self.currentHeartRate = value
                    self.sendToPhone(heartRate: value)
                }
            }
        }
    }
    
    func workoutBuilderDidCollectEvent(_ workoutBuilder: HKLiveWorkoutBuilder) {}
}

struct ContentView: View {
    @StateObject private var hrManager = WatchHeartRateManager()
    
    var body: some View {
        VStack(spacing: 12) {
            Text("❤️ Cardio Watch")
                .font(.headline)
                .foregroundColor(.red)
            
            if hrManager.isMeasuring {
                VStack {
                    Text("\(Int(hrManager.currentHeartRate))")
                        .font(.system(size: 40, weight: .black, design: .rounded))
                        .foregroundColor(.red)
                    Text("BPM")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundColor(.gray)
                }
                .transition(.scale)
                
                Button(action: {
                    hrManager.stopMeasurement()
                }) {
                    Text("Stop")
                        .fontWeight(.bold)
                        .foregroundColor(.white)
                }
                .background(Color.red.cornerRadius(10))
            } else {
                Text("Ready to start monitoring")
                    .font(.footnote)
                    .multilineTextAlignment(.center)
                    .foregroundColor(.gray)
                    .padding(.horizontal)
                
                Button(action: {
                    hrManager.startMeasurement()
                }) {
                    Text("Start")
                        .fontWeight(.bold)
                        .foregroundColor(.white)
                }
                .background(Color.green.cornerRadius(10))
            }
            
            Text("Status: \(hrManager.systemStatus)")
                .font(.system(size: 10))
                .foregroundColor(.secondary)
        }
        .padding()
    }
}

#Preview {
    ContentView()
}
