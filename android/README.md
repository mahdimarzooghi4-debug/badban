# Badban Android Preview APK (non-operational)

This is a **downloadable Android WebView wrapper** for the existing read-only
four-environment Badban preview at https://badban-ui-preview.onrender.com/.
It is **not** an independently implemented native application or a release candidate.

## Security and scope

- HTTPS only. The WebView navigates only to the exact preview homepage.
- External HTTPS links open in the device browser, not inside the wrapper.
- No native permissions except INTERNET. No SMS, contacts, location, camera,
  national-ID access, payment, transfers, guarantees, or backend integration.
- No OIDC, Keycloak, login bypass, token spoofing, API emulator, or simulated payment.
- The rendered content is clearly sample/read-only. **An internet connection is required.**
- JavaScript and DOM storage are enabled only because the preview is a React SPA.
- No JavaScript bridge, file access, cleartext HTTP, or SSL error bypass.
- On Android 7.0+ (minSdk 24).

## Build

The GitHub Actions workflow **Android Preview APK** builds the debug-signed APK
on its PR, uploads an artifact named `badban-android-preview-apk`, and prints
its SHA-256 digest. This workflow does **not** deploy a Render service, create
a Render preview environment, or publish to Play Store.

Run locally with JDK 17, Android SDK Platform 35, Android Build Tools 35 and Gradle 8.9:

```shell
cd android
gradle :app:assembleDebug --no-daemon
```

Output: `android/app/build/outputs/apk/debug/app-debug.apk`.

This is a **debug-signed** APK for visual testing and sideloading.
Never market it as a store-distributed, trusted, signed Production application.
A future Play Store application needs a private, owner-controlled release key,
app identity, security review, real-device tests, and explicit release approval.
