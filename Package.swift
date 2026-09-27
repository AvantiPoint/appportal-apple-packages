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
        .binaryTarget(name: "AppPortalTelemetry", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.174-g932ff14073/AppPortalTelemetry-3.0.174-g932ff14073.xcframework.zip", checksum: "9355ea8a91cf6562562c5d55b68d546e0547457ec3ea9fff7d9bd52b31a5a133"),
        .binaryTarget(name: "AppPortalMessaging", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.174-g932ff14073/AppPortalMessaging-3.0.174-g932ff14073.xcframework.zip", checksum: "56121e3ffdeb6dbe616b3c3d62c04340ec0b5a4d09a290fa7289805ffef33bfa"),
        .binaryTarget(name: "AppPortalLocation", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.174-g932ff14073/AppPortalLocation-3.0.174-g932ff14073.xcframework.zip", checksum: "c3f2283380dc78698916881c8ee6aa68deb26b50ae82d4c6d4a536a5ceeb2f71"),
        .binaryTarget(name: "AppPortalSmartLinks", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.174-g932ff14073/AppPortalSmartLinks-3.0.174-g932ff14073.xcframework.zip", checksum: "6d00bec6da986be65f6a0dee16c71f0304311ae4031106d19b9119f3a524a817")
    ]
)
