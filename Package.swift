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
        .binaryTarget(name: "AppPortalTelemetry", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.143-gf78d4d4c13/AppPortalTelemetry-3.0.143-gf78d4d4c13.xcframework.zip", checksum: "b6a6993e8969b431f15dd4c8a992be244e313be50d9934dfd0dc79b1082ad061"),
        .binaryTarget(name: "AppPortalMessaging", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.143-gf78d4d4c13/AppPortalMessaging-3.0.143-gf78d4d4c13.xcframework.zip", checksum: "b6e43e8609b1c5b4d6a3f80b5a64d434431b94e29031be30325fb883f1dec796"),
        .binaryTarget(name: "AppPortalLocation", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.143-gf78d4d4c13/AppPortalLocation-3.0.143-gf78d4d4c13.xcframework.zip", checksum: "c2aa01e88b06133558640a3a2db2cae25cd31838dd2f44f957faf5b1df4fc4aa"),
        .binaryTarget(name: "AppPortalSmartLinks", url: "https://github.com/AvantiPoint/appportal-apple-packages/releases/download/v3.0.143-gf78d4d4c13/AppPortalSmartLinks-3.0.143-gf78d4d4c13.xcframework.zip", checksum: "b850ae68bb61050e85a6f06c6b2ea62768f4c455d9abf35c938d59dd8668338b")
    ]
)
