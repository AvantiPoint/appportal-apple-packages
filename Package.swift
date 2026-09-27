// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AppPortalApple",
    platforms: [.iOS(.v13), .macOS(.v11), .tvOS(.v13), .watchOS(.v6), .macCatalyst(.v13)],
    products: [
        .library(name: "AppPortalTelemetry", targets: ["AppPortalTelemetry"]),
        .library(name: "AppPortalMessaging", targets: ["AppPortalTelemetry", "AppPortalMessaging"]),
        .library(name: "AppPortalLocation", targets: ["AppPortalTelemetry", "AppPortalLocation"]),
        .library(name: "AppPortalSmartLinks", targets: ["AppPortalTelemetry", "AppPortalSmartLinks"])
    ],
    targets: [
        .binaryTarget(name: "AppPortalTelemetry", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.169-g867c40caf4/AppPortalTelemetry-3.0.169-g867c40caf4.xcframework.zip", checksum: "7274e9ac419b87cf6cad77cadb4989aeaa3f8f7438fc154f795b74e36eb31341"),
        .binaryTarget(name: "AppPortalMessaging", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.169-g867c40caf4/AppPortalMessaging-3.0.169-g867c40caf4.xcframework.zip", checksum: "135c07b499c76f9954db60c1a6941a6bdacf0c828fab7732a3d827b3331c223a"),
        .binaryTarget(name: "AppPortalLocation", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.169-g867c40caf4/AppPortalLocation-3.0.169-g867c40caf4.xcframework.zip", checksum: "247b6adba837c40c5d4e9d4907f2c684a327587274c393b159885fd017d3cb7d"),
        .binaryTarget(name: "AppPortalSmartLinks", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.169-g867c40caf4/AppPortalSmartLinks-3.0.169-g867c40caf4.xcframework.zip", checksum: "6ff9aa23dd5dbd2461f0e4d4c2a062b4fb841b5ca4e08987b9a880c67fa6269d")
    ]
)
