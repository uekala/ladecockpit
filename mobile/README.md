# Ladecockpit Mobile (iOS + Android)

Flutter client for the existing Ladecockpit FastAPI service.

## Current scope

- Shared Flutter codebase for iOS and Android.
- Reads the existing `GET /api/dashboard` endpoint.
- Connection URL and app password are stored using the platform secure-storage plugin.
- Intended for private access over an existing Tailscale connection; no public port forwarding is required.
- Automotive dark design: central theme tokens in `lib/theme/app_theme.dart`, rules and colour table in [`docs/mobile-automotive-design-system.md`](../docs/mobile-automotive-design-system.md). The dashboard is split into three tabs (Cockpit, Ladevorgänge, Auswertung) with a bottom navigation bar.

## Local development

Install Flutter (stable), then:

```sh
cd mobile
flutter pub get
flutter analyze
flutter run
```

## Connection setup

In the app, enter the Ladecockpit URL reachable from the phone over Tailscale, for example:

```
http://100.x.y.z:8077
```

Use the actual Tailscale IP or MagicDNS hostname and the port configured for the Ladecockpit service. Prefer HTTPS through Tailscale Serve or a reverse proxy. If you use plain HTTP, keep the endpoint reachable only inside your trusted Tailscale network; never expose it publicly.

The app accepts plain HTTP only for addresses that do not cross the open internet: Tailscale (`100.64.0.0/10`, `*.ts.net`, `fd7a:115c:a1e0::/48`), private home networks (`10.x`, `172.16–31.x`, `192.168.x`, `fc00::/7`), and local names (`*.local`, `*.home.arpa`, `*.internal`, names without a dot). Every other address needs HTTPS.

For a live standalone/Docker installation, `APP_PASSWORD` is required by default. Enter the same password in the app; it is stored in platform secure storage, not in source code.

### Home Assistant add-on: secure direct access

Home Assistant Ingress is protected by Home Assistant authentication, but a separately exposed add-on port is a different entry point. The mobile app connects to that direct endpoint; it cannot use the browser's Ingress session.

For add-on versions that include the `mobile_app_password` option:

1. Open the Ladecockpit add-on configuration and set a strong, unique **Mobile App Password**.
2. Save the configuration and restart the add-on so the password is applied.
3. Only then enable the add-on's network mapping for `8077/tcp` (host port 8077, or another private host port if preferred).
4. Keep that port reachable only on your trusted LAN/Tailscale network. Do not create a router port-forward or expose it to the public internet.
5. In the mobile app, enter the Home Assistant host's Tailscale IP or MagicDNS name and the mapped port, plus the same Mobile App Password.

The port mapping is disabled by default. Do not enable it before setting the password. If the option is not visible in the add-on configuration, the installed add-on version does not yet contain this feature; do not work around this by exposing the port without authentication.

## Build

```sh
flutter build apk --release
flutter build appbundle --release
flutter build ios --release --no-codesign
```

An iOS archive suitable for TestFlight/App Store distribution still requires Apple signing credentials and provisioning. Android Play distribution requires a separately configured signing key.

## Android updates and signing

Android only installs an update over an existing app when both are signed with the same key and the build number (`versionCode`) is higher. CI regenerates the Android project with `flutter create` on every run; without its own configuration Flutter signs release builds with the runner's random debug key. That is why a new APK could not be installed over an installed one.

How it works now:

- `tool/configure-android-signing.py` signs release builds with a persistent upload key from GitHub Actions secrets. Passwords stay in environment variables; nothing is written to the repository. The keystore is deleted from the runner after the build.
- The build number is the workflow run number + 1, so it rises with every build.
- `tool/verify-apk-signature.sh` fails the build if a signed APK carries a debug key or, when the repository variable `ANDROID_SIGNING_CERT_SHA256` is set, any other certificate.
- Without the secrets (for example in pull requests from Dependabot) the build still runs, carries the debug key and is marked as a test build that cannot be installed as an update. A manual run with **release** enabled fails instead.

One-time setup and verification (by the repository owner; never commit the key or paste it into a chat):

1. **Create the key and the secrets on your own computer** (Linux, macOS, or Git Bash/WSL on Windows; needs `keytool` from a JDK and a logged-in `gh`):
   `bash mobile/tool/setup-android-signing.sh uekala/ladecockpit`
   The script asks for a password, creates `ladecockpit-upload.jks` (or reuses an existing one), sets the four secrets and the variable `ANDROID_SIGNING_CERT_SHA256`. It refuses to run if the repository already has a key, because a second key would break updates.
2. **Back up** the keystore file and the password (password manager plus an offline copy). Without them no further updates are possible.
3. **First signed build:** `gh workflow run "Mobile app builds" --repo uekala/ladecockpit --ref main -f release=true`. In the run summary, the section "Android-Signatur" must show the certificate and "Abgleich mit `ANDROID_SIGNING_CERT_SHA256`: ok".
4. Download the APK (`gh run download <run-id> --repo uekala/ladecockpit -n ladecockpit-android-apk`), uninstall the currently installed app once, then `adb install app-release.apk`.
5. **Update test:** start the workflow a second time, download the new APK and run `adb install -r app-release.apk`. It must report `Success`; `adb shell dumpsys package io.github.uekala.ladecockpit | grep versionCode` shows the higher build number. Only then is the signing fix verified.

Note: the Android application ID and the iOS bundle identifier are `io.github.uekala.ladecockpit` (set with `--org io.github.uekala` in `flutter create`; CI checks both). The ID must not change any more: a build with another ID installs as a second app instead of an update. If you still have a build with the old ID `com.example.ladecockpit` on your phone, uninstall it once.
