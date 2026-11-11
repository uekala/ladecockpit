# Ladecockpit Mobile (iOS + Android)

Flutter client for the existing Ladecockpit FastAPI service.

## Current scope

- Shared Flutter codebase for iOS and Android.
- Reads the existing `GET /api/dashboard` endpoint.
- Connection URL and app password are stored using the platform secure-storage plugin.
- Intended for private access over an existing Tailscale connection; no public port forwarding is required.

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

One-time setup (by the repository owner; never commit the key or paste it into a chat):

1. `keytool -genkeypair -v -keystore ladecockpit-upload.jks -keyalg RSA -keysize 4096 -validity 10000 -alias upload`
2. Store the keystore and both passwords safely (password manager plus an offline copy). Without this key no further updates are possible.
3. `base64 -w0 ladecockpit-upload.jks | gh secret set ANDROID_KEYSTORE_BASE64`, then `gh secret set ANDROID_KEYSTORE_PASSWORD`, `gh secret set ANDROID_KEY_ALIAS` (value `upload`) and `gh secret set ANDROID_KEY_PASSWORD`.
4. `keytool -list -v -keystore ladecockpit-upload.jks -alias upload | grep SHA256`, then `gh variable set ANDROID_SIGNING_CERT_SHA256 --body "<value>"`.
5. Uninstall the currently installed app once; from then on every signed build installs as an update.
