# Ladecockpit Mobile (iOS + Android)

Flutter client for the existing Ladecockpit FastAPI service.

## Current scope

- Shared Flutter codebase for iOS and Android.
- Reads the existing `GET /api/dashboard` endpoint.
- Connection URL and optional app password are stored using the platform secure-storage plugin.
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
http://100.x.y.z:8000
```

Use the actual Tailscale IP or MagicDNS hostname and the port configured for the Ladecockpit service. If HTTP is used, traffic remains inside the encrypted Tailscale tunnel. Do not expose this endpoint publicly.

If Ladecockpit's optional `APP_PASSWORD` is enabled, enter that password in the app. It is stored in the device secure storage, not in source code.

## Build

```sh
flutter build apk --release
flutter build appbundle --release
flutter build ios --release --no-codesign
```

An iOS archive suitable for TestFlight/App Store distribution still requires Apple signing credentials and provisioning. Android Play distribution requires a separately configured signing key.

## Next steps

1. Map all dashboard response fields to polished, typed mobile widgets.
2. Add charging-session history, invoices and reports using the existing API routes.
3. Add connection diagnostics and an explicit reconnect state.
4. Add push notifications only after choosing a secure notification delivery design.
5. Configure signed release pipelines after signing credentials are supplied securely via repository secrets (never commit them).
