# Ladecockpit

**Deine echten Supercharger-Rechnungen in Home Assistant – plus eine kleine Web-App, die zeigt, was Laden wirklich kostet.**

[English](README.md)

![Ladecockpit-Web-App mit Demo-Daten](docs/screenshot.png)

Viele Home-Assistant-Setups schätzen die Supercharger-Kosten aus den kWh des Autos und einem festen Preis oder fragen nach jeder Ladung den Preis ab. Ladecockpit holt stattdessen die echte Rechnung über die Tesla Fleet API: abgerechnete kWh, Preis pro kWh, Blockiergebühr, Standort und PDF. Diese Daten gibt es an Home Assistant weiter.

## Funktionen

- **Echte Rechnungen, automatisch.** Ladecockpit erkennt das Ladeende, holt die Rechnung innerhalb weniger Minuten und meldet sie genau einmal an Home Assistant. Ein Blueprint bucht sie in deine eigenen Helfer.
- **Preis-Radar.** Zeigt aus deinen eigenen Rechnungen, zu welcher Uhrzeit und an welchem Supercharger du am günstigsten lädst.
- **MultiPass.** Fremde Ladesäulen, die über Tesla MultiPass bezahlt werden, erkennt Ladecockpit in den Tesla-Rechnungen und weist sie getrennt aus, mit eigenem Ø-Preis.
- **Nächster Ladestopp.** Sagt anhand deines Verbrauchs voraus, wann der Akku die Untergrenze erreicht (Standard: 10 %), und wann und wo du vorher am günstigsten lädst: die beste Kombination aus Supercharger und Uhrzeit aus deinen eigenen Rechnungen.
- **Monatsübersicht.** Kosten, kWh, Ø-Preis, Kosten pro 100 km/mi, optional Vergleich mit einem Referenzpreis oder den Spritkosten eines zweiten Autos.
- **Ersparnis ggü. Verbrenner.** Was dieselbe Strecke mit Benzin oder Diesel gekostet hätte (feste Werte oder live aus Home Assistant, z. B. ein Spritpreis-Sensor), pro Monat und aufs Jahr hochgerechnet.
- **Monatsbericht.** Am Monatsersten eine Zusammenfassung des Vormonats als Event und Benachrichtigung in Home Assistant.
- **Ladeleistung und Verbrauch.** Ø kW pro Ladung und pro Supercharger, kWh pro 100 km/mi inklusive Ladeverlusten.
- **Abgleich.** Vergleicht deine Summen in Home Assistant mit den Rechnungen.
- **Export.** Alle Ladungen als CSV, alle Rechnungen eines Monats als ein ZIP.
- **Problem-Meldung.** Benachrichtigung in Home Assistant, wenn die Tesla-Anmeldung abläuft oder der Abgleich wiederholt fehlschlägt.
- **Sensoren fürs Dashboard.** Nächster Ladestopp, Akku, Monatskosten, letzte Ladung und Preistipp als Entitäten in Home Assistant, dazu eine fertige Dashboard-Sektion.
- **Funktioniert auch offline.** Speichert einen eigenen Verlauf von Akkustand und Kilometerstand, z. B. für ein Auto in der Tiefgarage ohne Empfang.
- **Sparsam bei der Tesla-API.** Live-Daten kommen aus Home Assistant. Tesla wird nur nach der Ladehistorie gefragt, ein paar Dutzend Abfragen im Monat.
- **Nur lesend.** Es gibt keinen Code, der Befehle ans Auto schickt oder es weckt.
- **Läuft als Home-Assistant-App** (Seitenleiste, kein extra Server) oder als Docker-Container überall.
- Deutsch und Englisch, Demo-Modus ohne Zugangsdaten, als App auf den Handy-Startbildschirm legbar.

## So funktioniert es

```
Home Assistant ──(Akku, Kilometerstand, Ladestatus)──► Ladecockpit ──(Ladehistorie)──► Tesla Fleet API
      ▲                                                     │
      └──────── Event "ladecockpit_invoice" ◄───────────────┘
                (Blueprint bucht kWh und Kosten in deine Helfer)
```

1. Ladecockpit fragt jede Minute ein paar Entitäten deines Autos in Home Assistant ab (lokal, kostenlos).
2. Wenn der Ladestatus `charging` verlässt, fragt es alle 10 Minuten die Ladehistorie bei Tesla ab, bis die neue Rechnung da ist (höchstens 3 Stunden). Sonst gleicht es alle 6 Stunden ab.
3. Jede neue Rechnung wird genau einmal als Event `ladecockpit_invoice` gemeldet.
4. Beim allerersten Abgleich werden alle bisherigen Rechnungen nur übernommen (in der App angezeigt) und **nicht** gemeldet. So werden Summen, die du schon in Home Assistant führst, nicht doppelt gezählt.

## Voraussetzungen

- Home Assistant OS oder Supervised (für die App), **oder** Docker auf einem Gerät, das rund um die Uhr läuft
- Ein Tesla-Konto und eine **Tesla Developer App** mit Fleet-API-Zugang
- Optional, aber empfohlen: Home Assistant mit einer Integration, die die Entitäten deines Autos bereitstellt (Tesla Fleet, Teslemetry, Tessie, …)

## Als Home-Assistant-App installieren (empfohlen)

[![Ladecockpit-Repository zu Home Assistant hinzufügen](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fuekala%2Fladecockpit)

1. Auf den Button klicken oder `https://github.com/uekala/ladecockpit` unter Einstellungen → Apps → App Store → ⋮ → Repositories hinzufügen.
2. **Ladecockpit** installieren. Im Reiter **Konfiguration** Tesla Client ID/Secret und die Entitäten deines Autos eintragen, dann starten.
3. **Ladecockpit** in der Seitenleiste öffnen und den drei Anmelde-Schritten dort folgen.
4. Rechnungen mit dem Blueprint buchen (siehe [Schritt 5](#5-rechnungen-in-home-assistant-buchen)).

Immer nur ein Ladecockpit gleichzeitig betreiben. Zwei Instanzen würden jede Rechnung doppelt melden. Details stehen in der [App-Dokumentation](ladecockpit-app/DOCS.md).

## Schnellstart mit Docker (Demo)

```bash
git clone https://github.com/uekala/ladecockpit.git
cd ladecockpit
cp .env.example .env      # für die deutsche Oberfläche: APP_LANG=de
docker compose up -d --build
```

`http://localhost:8077` öffnen. Ohne Zugangsdaten läuft die App mit Beispieldaten.

## Einrichtung

### 1. Tesla Developer App

Nutzt du schon die Tesla-Fleet-Integration in Home Assistant (oder ein anderes Fleet-API-Tool) mit eigener Developer App, kannst du sie weiterverwenden:

1. Auf [developer.tesla.com](https://developer.tesla.com) deine App öffnen.
2. `http://localhost:8077/auth/callback` unter **Zulässige Weiterleitungs-URI(s)** hinzufügen.
3. Prüfen, dass der Scope **Vehicle Charging Management** (Ladeverwaltung) aktiviert ist. Tesla bündelt darin Ladehistorie und Lade-Befehle. Ladecockpit liest nur.
4. Client ID und Secret notieren.

Fängst du ganz neu an? Die Fleet API antwortet nur Apps, deren Domain mit einem Public Key registriert ist. Die [Doku der Tesla-Fleet-Integration von Home Assistant](https://www.home-assistant.io/integrations/tesla_fleet/) erklärt, wie man die App anlegt und den Schlüssel registriert. Teslas eigene Schritte stehen in der [Fleet-API-Doku](https://developer.tesla.com/docs/fleet-api).

### 2. Konfigurieren

```bash
cp .env.example .env
```

Mindestens nötig: `TESLA_CLIENT_ID`, `TESLA_CLIENT_SECRET`, `HA_URL`, `HA_TOKEN` (Home Assistant → Profil → Sicherheit → Langlebige Zugriffstoken) und die Entitäten deines Autos:

| Einstellung | Beispiel | Schaltet frei |
|---|---|---|
| `HA_ENT_SOC` | `sensor.my_tesla_battery_level` | Akku-Anzeige, Prognose |
| `HA_ENT_RANGE` | `sensor.my_tesla_battery_range` | Reichweite |
| `HA_ENT_ODOMETER` | `sensor.my_tesla_odometer` | Strecke pro Monat, Kosten pro 100 km/mi |
| `HA_ENT_CHARGING` | `sensor.my_tesla_charging` | Rechnung direkt nach dem Ladeende |

Für die deutsche Oberfläche `APP_LANG=de` setzen. Bei `HA_URL` die IP von Home Assistant eintragen, denn `.local`-Namen werden im Container oft nicht aufgelöst. Alle Einstellungen stehen in [.env.example](.env.example).

### 3. Starten

```bash
docker compose up -d --build
docker compose logs -f      # erwartet: "Ladecockpit … started (live, …)"
```

Alternativ das fertige Image nutzen (siehe `docker-compose.yml`): `ghcr.io/uekala/ladecockpit:latest` für amd64 und arm64.

### 4. Mit Tesla verbinden

Auf dem Rechner, auf dem der Container läuft, `http://localhost:8077` öffnen und **Bei Tesla anmelden** klicken. Danach startet sofort der erste Abgleich.

Die Redirect-URI zeigt auf `localhost`. Läuft der Container woanders, gibt es zwei Wege:
- Einen SSH-Tunnel öffnen: `ssh -L 8077:localhost:8077 dein-server`.
- Nach der Anmeldung die komplette Adresse aus der Browserzeile kopieren und unter „Die Weiterleitung nach der Anmeldung landet nicht hier?“ einfügen. Die Seite selbst lädt dann nicht, das ist in Ordnung.

### 5. Rechnungen in Home Assistant buchen

1. Zwei **Zahlen**-Helfer anlegen (Einstellungen → Geräte & Dienste → Helfer), z. B. „Lademenge gesamt“ (kWh) und „Ladekosten gesamt“. Das **Maximum hoch** setzen (z. B. 1000000), denn der Standardwert 100 ist schnell erreicht. Optional einen **Text**-Helfer für die letzte Ladung anlegen.
2. Blueprint importieren:

   [![Home Assistant öffnen und den Blueprint-Import mit diesem Blueprint starten.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fuekala%2Fladecockpit%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fladecockpit%2Fbook_invoice.yaml)

3. Daraus eine Automation erstellen und die Helfer auswählen. Unter *Additional actions* kannst du z. B. eine Benachrichtigung ergänzen. Dort stehen die Variablen `site`, `kwh`, `total`, `price_per_kwh`, `idle_fee`, `currency`, `network` und `text` zur Verfügung.
4. `HA_ENT_COST_TOTAL` und `HA_ENT_KWH_TOTAL` auf die beiden Helfer setzen, dann zeigt die App den Abgleich.

Optional: [`homeassistant/ladecockpit_package.yaml`](homeassistant/ladecockpit_package.yaml) bringt einen `rest_command`, um die Rechnungssuche selbst anzustoßen.

### 6. Sensoren und Dashboard

Ladecockpit legt diese Entitäten in Home Assistant selbst an (abschaltbar mit der App-Option `publish_entities` bzw. `PUBLISH_ENTITIES=false`):

| Entität | Zustand | Nützliche Attribute |
|---|---|---|
| `sensor.ladecockpit_next_charge` | Datum des nächsten Ladestopps | `text`, `days`, `plan` (wann und wo laden), `plan_saving` |
| `sensor.ladecockpit_battery` | Akkustand in %, bei Funkstille der letzte bekannte Wert | `range`, `last_known`, `as_of` |
| `sensor.ladecockpit_month_cost` | Ladekosten im laufenden Monat | `energy_kwh`, `price_per_kwh`, `cost_per_100`, `kwh_per_100`, `multipass_cost`, `savings`, `projected_year_cost`, `previous_cost` |
| `sensor.ladecockpit_last_charge` | Kosten der letzten Ladung | `network`, `site`, `energy_kwh`, `price_per_kwh`, `avg_power_kw`, `text` |
| `sensor.ladecockpit_price_tip` | deine günstigste Uhrzeit als Satz | `best_time`, `best_site`, `insights` |
| `binary_sensor.ladecockpit_problem` | `on`, wenn die Tesla-Anmeldung abgelaufen ist, der Abgleich fehlschlägt oder eine Entität fehlt | `kind`, `message`, `last_sync` |

Sie werden über die REST-API geschrieben und haben keine eindeutige ID, lassen sich also nicht in der Oberfläche umbenennen. Nach einem Neustart von Home Assistant sind sie nach wenigen Minuten wieder da. Eine fertige Dashboard-Sektion steht in [`homeassistant/dashboard_card.yaml`](homeassistant/dashboard_card.yaml).

### Monatsbericht

Am Monatsersten feuert Ladecockpit `ladecockpit_month_report` mit den Zahlen des Vormonats: `label`, `sessions`, `kwh`, `cost`, `price_per_kwh`, `distance`, `cost_per_100`, `kwh_per_100`, `multipass_cost`, `idle_fees`, `fuel_equivalent`, `savings`, `title` und `text` (ein fertiger Satz). Mit der Option `month_report` bzw. `MONTH_REPORT` gibt es zusätzlich eine Benachrichtigung in Home Assistant. Aufs Handy:

```yaml
triggers:
  - trigger: event
    event_type: ladecockpit_month_report
actions:
  - action: notify.mobile_app_dein_handy
    data:
      title: "{{ trigger.event.data.title }}"
      message: "{{ trigger.event.data.text }}"
```

### MultiPass

Tesla rechnet MultiPass-Ladungen (fremde Ladesäulen, bezahlt über dein Tesla-Konto) über dieselbe Ladehistorie ab wie Supercharger-Ladungen. Die Fleet API hat kein Feld, das das Netz nennt, und Tesla hat nicht dokumentiert, wie solche Ladungen aussehen. Ladecockpit geht deshalb nach Hinweisen: eine andere Abrechnungs- oder Rechnungsart als bei Supercharger-Ladungen, Begriffe wie „roaming“ oder „partner“ in Teslas Feldern oder der Name eines bekannten Betreibers (IONITY, EnBW, Fastned, …) im Standortnamen. Die Regel wird bei jedem Lesen angewandt, eine verbesserte Regel in einer späteren Version ordnet also auch ältere Ladungen neu ein.

Wird eine MultiPass-Ladung als Supercharger angezeigt (oder umgekehrt), bitte ein Issue mit der anonymisierten Ausgabe von `/api/debug/raw` für diese Ladung aufmachen. Im Log steht außerdem, welche Felder Ladecockpit noch nicht kennt.

## Kosten

Die Fleet API wird pro Abfrage abgerechnet. Ladecockpit nutzt nur Datenabfragen für Ladehistorie und Rechnungen. Mit den Standardeinstellungen sind das ein paar Dutzend Abfragen im Monat, weit innerhalb des monatlichen Guthabens, das Tesla jedem Entwicklerkonto gibt. `API_BUDGET_REQUESTS` (Standard 1500) ist eine harte Obergrenze. Die App zeigt den Zählerstand des laufenden Monats.

## Datenschutz und Sicherheit

- Alles bleibt bei dir: Tokens, Rechnungen und Messwerte liegen im Docker-Volume `ladecockpit-data` (SQLite und PDF-Cache).
- Ladecockpit spricht nur mit Tesla und deinem Home Assistant.
- Im LAN oder hinter einem Reverse-Proxy mit Anmeldung betreiben. `APP_PASSWORD` gibt einen einfachen HTTP-Basic-Schutz.
- Die eigene `.env` nie committen. Sie steht bereits in `.gitignore`.

## Fehlersuche

- **„Entität in Home Assistant nicht gefunden“**: die `HA_ENT_…`-Einstellungen unter Entwicklerwerkzeuge → Zustände prüfen.
- **Rechnungsbeträge fehlen oder sind 0**: `/api/debug/raw` öffnen und die Felder mit dem vergleichen, was `app/tesla.py` liest. Gern ein Issue mit anonymisiertem Beispiel aufmachen.
- **„Tesla-Anmeldung abgelaufen“**: Refresh-Tokens sind nur einmal gültig und laufen nach längerer Nichtnutzung ab. Einfach neu verbinden.

## Hinweis

Ladecockpit ist ein Community-Projekt und steht in keiner Verbindung zu Tesla, Inc. Tesla und Supercharger sind Marken von Tesla, Inc. Nutzung auf eigene Verantwortung. Im Zweifel die Rechnungen in der Tesla-App prüfen.

## Lizenz

[MIT](LICENSE)
