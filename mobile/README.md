# Ladecockpit Mobil (iOS + Android)

Flutter-App für den bestehenden FastAPI-Dienst von Ladecockpit.

## Umfang

- Gemeinsamer Flutter-Code für iOS und Android.
- Liest den bestehenden Endpunkt `GET /api/dashboard`.
- Verbindungsadresse und App-Passwort liegen im sicheren Speicher der Plattform.
- Gedacht für privaten Zugriff über eine bestehende Tailscale-Verbindung; eine öffentliche Portweiterleitung ist nicht nötig.
- Dunkles Fahrzeug-Design: zentrale Theme-Werte in `lib/theme/app_theme.dart`, Regeln und Farbtabelle in [`docs/mobile-automotive-design-system.md`](../docs/mobile-automotive-design-system.md). Das Dashboard ist in drei Tabs aufgeteilt (Cockpit, Ladevorgänge, Auswertung) mit einer Navigationsleiste unten.

## Lokale Entwicklung

Flutter (stable) installieren, dann:

```sh
cd mobile
flutter pub get
flutter analyze
flutter run
```

## Verbindung einrichten

In der App die Adresse von Ladecockpit eintragen, die das Handy über Tailscale erreicht, zum Beispiel:

```
http://100.x.y.z:8077
```

Die echte Tailscale-IP oder den MagicDNS-Namen und den Port des Ladecockpit-Dienstes verwenden. Besser ist HTTPS über Tailscale Serve oder einen Reverse-Proxy. Bei unverschlüsseltem HTTP den Endpunkt nur im vertrauenswürdigen Tailscale-Netz erreichbar halten und nie öffentlich freigeben.

Unverschlüsseltes HTTP akzeptiert die App nur für Adressen, die nicht über das offene Internet laufen: Tailscale (`100.64.0.0/10`, `*.ts.net`, `fd7a:115c:a1e0::/48`), private Heimnetze (`10.x`, `172.16–31.x`, `192.168.x`, `fc00::/7`) und lokale Namen (`*.local`, `*.home.arpa`, `*.internal`, Namen ohne Punkt). Jede andere Adresse braucht HTTPS.

Eine Live-Installation im Standalone- oder Docker-Betrieb verlangt standardmäßig `APP_PASSWORD`. Dasselbe Passwort in der App eintragen; es liegt im sicheren Speicher der Plattform, nicht im Quellcode.

### Home-Assistant-App: sicherer direkter Zugriff

Ingress ist durch die Anmeldung von Home Assistant geschützt, ein eigens freigegebener Port der App ist aber ein anderer Zugang. Die Handy-App verbindet sich mit diesem direkten Endpunkt; die Ingress-Sitzung des Browsers kann sie nicht nutzen.

Für Versionen der App mit der Option `mobile_app_password`:

1. In der Konfiguration der Ladecockpit-App ein starkes, einmaliges **Mobiles App-Passwort** setzen.
2. Konfiguration speichern und die App neu starten, damit das Passwort gilt.
3. Erst dann die Netzwerkfreigabe für `8077/tcp` einschalten (Host-Port 8077 oder ein anderer privater Host-Port).
4. Den Port nur im vertrauenswürdigen LAN bzw. Tailscale-Netz erreichbar halten. Keine Portweiterleitung im Router anlegen und ihn nicht ins öffentliche Internet stellen.
5. In der Handy-App die Tailscale-IP oder den MagicDNS-Namen des Home-Assistant-Hosts und den freigegebenen Port eintragen, dazu dasselbe Mobile App-Passwort.

Die Portfreigabe ist standardmäßig aus. Nicht einschalten, bevor das Passwort gesetzt ist. Fehlt die Option in der Konfiguration, enthält die installierte Version die Funktion noch nicht; dann den Port nicht ohne Anmeldung freigeben.

## Bauen

```sh
flutter build apk --release
flutter build appbundle --release
flutter build ios --release --no-codesign
```

Ein iOS-Archiv für TestFlight oder den App Store braucht weiterhin Signierdaten und ein Provisioning von Apple. Für den Play Store ist ein eigens eingerichteter Signierschlüssel nötig.

## Android-Updates und Signierung

Android installiert ein Update über eine vorhandene App nur, wenn beide mit demselben Schlüssel signiert sind und die Build-Nummer (`versionCode`) höher ist. Die CI erzeugt das Android-Projekt bei jedem Lauf neu mit `flutter create`; ohne eigene Konfiguration signiert Flutter Release-Builds mit dem zufälligen Debug-Schlüssel des Runners. Deshalb ließ sich eine neue APK nicht über eine installierte installieren.

So funktioniert es jetzt:

- `tool/configure-android-signing.py` signiert Release-Builds mit einem dauerhaften Upload-Schlüssel aus den Secrets von GitHub Actions. Passwörter bleiben in Umgebungsvariablen; ins Repository wird nichts geschrieben. Der Keystore wird nach dem Build vom Runner gelöscht.
- Die Build-Nummer ist die Laufnummer des Workflows + 1 und steigt so mit jedem Build.
- `tool/verify-apk-signature.sh` lässt den Build scheitern, wenn eine signierte APK einen Debug-Schlüssel trägt oder, falls die Repository-Variable `ANDROID_SIGNING_CERT_SHA256` gesetzt ist, ein anderes Zertifikat.
- Ohne die Secrets (zum Beispiel bei Pull Requests aus einem Fork) läuft der Build trotzdem, trägt den Debug-Schlüssel und ist als Test-Build gekennzeichnet, der sich nicht als Update installieren lässt. Ein Lauf von Hand mit **release** schlägt dagegen fehl.

Einmalige Einrichtung und Prüfung (durch den Besitzer des Repositorys; den Schlüssel nie committen oder irgendwo einfügen):

1. **Schlüssel und Secrets auf dem eigenen Rechner anlegen** (Linux, macOS oder Git Bash/WSL unter Windows; braucht `keytool` aus einem JDK und ein angemeldetes `gh`):
   `bash mobile/tool/setup-android-signing.sh uekala/ladecockpit`
   Das Skript fragt nach einem Passwort, legt `ladecockpit-upload.jks` an (oder nimmt eine vorhandene Datei), setzt die vier Secrets und die Variable `ANDROID_SIGNING_CERT_SHA256`. Hat das Repository schon einen Schlüssel, bricht es ab, weil ein zweiter Schlüssel die Updates kaputt machen würde.
2. Keystore-Datei und Passwort **sichern** (Passwortmanager und eine Offline-Kopie). Ohne sie sind keine weiteren Updates möglich.
3. **Erster signierter Build:** `gh workflow run "Mobile app builds" --repo uekala/ladecockpit --ref main -f release=true`. In der Zusammenfassung des Laufs muss der Abschnitt „Android-Signatur“ das Zertifikat zeigen und „Abgleich mit `ANDROID_SIGNING_CERT_SHA256`: ok“.
4. Die APK herunterladen (`gh run download <run-id> --repo uekala/ladecockpit -n ladecockpit-android-apk`), die installierte App einmal deinstallieren, dann `adb install app-release.apk`.
5. **Update-Test:** den Workflow ein zweites Mal starten, die neue APK herunterladen und `adb install -r app-release.apk` ausführen. Es muss `Success` melden; `adb shell dumpsys package io.github.uekala.ladecockpit | grep versionCode` zeigt die höhere Build-Nummer. Erst dann ist die Signierung bestätigt.

**Releases:** Wird auf GitHub ein Release veröffentlicht, baut der Workflow die APK mit dem Release-Schlüssel (fehlt er, bricht er ab), benennt sie nach dem Release (`ladecockpit-0.12.7.apk`, Versionsname aus dem Tag) und hängt sie mit ihrer SHA-256-Prüfsumme an das Release. Release-Builds tragen außerdem die Version (`--dart-define=LADECOCKPIT_VERSION`); damit fragt die Android-App einmal pro Start bei `api.github.com` nach dem neuesten Release und zeigt ein Banner mit Download-Knopf, wenn es neuer ist. Test-Builds haben keine Version und prüfen nie. In den Verbindungseinstellungen lässt sich die Prüfung abschalten.

Hinweis: Die Android-App-ID und die iOS-Bundle-ID sind `io.github.uekala.ladecockpit` (gesetzt mit `--org io.github.uekala` in `flutter create`; die CI prüft beide). Die ID darf sich nicht mehr ändern: Ein Build mit anderer ID installiert sich als zweite App statt als Update. Ist noch ein Build mit der alten ID `com.example.ladecockpit` auf dem Handy, diesen einmal deinstallieren.
