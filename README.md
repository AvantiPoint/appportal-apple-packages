# AppPortal for Apple platforms

Install precompiled AppPortal libraries with Swift Package Manager. This package contains binary
frameworks and public API interfaces; access to the AppPortal implementation repository is not required.

In Xcode, choose **File → Add Package Dependencies**, enter
`https://github.com/AvantiPoint/appportal-apple-packages`, select a published release, and add the
products your app uses:

| Product and import | Use it for |
| --- | --- |
| `AppPortalTelemetry` | Events, identity, sessions, errors, logs, and performance |
| `AppPortalMessaging` | Push tokens and Message Center |
| `AppPortalLocation` | Geofence synchronization and location event delivery |
| `AppPortalSmartLinks` | Resolve approved links and route them inside your app |

The optional products include the shared Telemetry framework, so configure Telemetry once.
Messaging and Location use its client and delivery queue. Smart Links has its own handler and
public resolver transport; usage events go through Telemetry. Your app owns notification permission,
Core Location monitoring, and navigation. Location does not yet provide the .NET geofence planning prototype.

Requires iOS/iPadOS 13, macOS 11, tvOS 13, watchOS 6, or Mac Catalyst 13 and later.
Each framework includes its device/simulator variants and privacy manifest.

```swift
import AppPortalTelemetry
import SwiftUI

@main
@MainActor
enum StoreEntryPoint {
    static func main() {
        AppPortal.start("<app-credential>")
        StoreApp.main()
    }
}

// Your existing SwiftUI App has no @main attribute; StoreEntryPoint owns startup.
struct StoreApp: App {
    var body: some Scene { WindowGroup { Text("Store") } }
}
```

For UIKit or AppKit, initialize in your entry point before `UIApplicationMain` or
`NSApplicationMain`. The SDK owns lifecycle observation, cold/warm startup timing, crash capture
and durable background delivery. Native initialization includes framework startup in the measured
interval; no application stopwatch, lifecycle forwarding or flush call is required. Choose navigation
observation separately for your app's navigation system.

When your consent policy permits collection, grant consent through `AppPortal.grantConsent()`
or set `options.initialConsentState = .granted` in the root configuration closure. When the app knows
the user, supply its chosen identifier. A separate name or profile is not required:

```swift
AppPortal.identify(userId: "customer-42")
AppPortal.trackEvent("item.saved", properties: ["category": "favorites"])
AppPortal.clearUser() // On sign-out.
```

For manual installation, download `AppPortalApple-<version>.zip` from the same release, unzip it,
and use **Add Local** in Xcode to select the `AppPortalApple` directory. Keep that directory with
your project so other developers and CI can resolve it. Do not add both the remote and local package.

Apps that evaluated the earlier internal source preview need three naming updates:

- Smart Link routing types now use `import AppPortalSmartLinks`.
- Messaging's static calls use `AppPortalMessages` within `import AppPortalMessaging`.
- Location's static calls use `AppPortalLocations` within `import AppPortalLocation`.

Method names and behavior are unchanged. Facade names differ from their modules so Swift can
import the binary interfaces without special compiler flags.

Preview binaries are unsigned unless the release metadata says otherwise; the app build signs
embedded frameworks with the app's identity. SwiftPM verifies each downloaded archive using its
SHA-256 checksum. See [the documentation](https://appportal.io/docs/sdks/apple/) for app setup.

Built with Xcode 26.6; Build version 17F113. Apple Swift version 6.3.3 (swiftlang-6.3.3.1.3 clang-2100.1.1.101); Target: arm64-apple-macosx26.0.
Use this Xcode toolchain or a compatible newer compiler. The Swift tools version
in Package.swift is the manifest format, not a minimum compiler guarantee.
