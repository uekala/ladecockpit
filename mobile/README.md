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
