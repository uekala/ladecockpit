# Ladecockpit

**Deine echten Supercharger-Rechnungen in Home Assistant – plus eine kleine Web-App, die zeigt, was Laden wirklich kostet.**

[English](README.md)

![Ladecockpit mit Demo-Daten, während das Auto lädt: am Desktop im dynamischen Design mit leuchtendem Akku-Ring, Leistung, Uhrzeit und Countdown bis zum Ladelimit, nächstem Ladestopp und letzter Rechnung; auf einem Handy das Preis-Radar des dynamischen Designs mit dem aktuellen Zeitfenster; auf einem zweiten Handy das klassische Design hell](docs/screenshot-de.png)

Viele Home-Assistant-Setups schätzen die Supercharger-Kosten aus den kWh des Autos und einem festen Preis oder fragen nach jeder Ladung den Preis ab. Ladecockpit holt stattdessen die echte Rechnung über die Tesla Fleet API: abgerechnete kWh, Preis pro kWh, Blockiergebühr, Standort und PDF. Diese Daten gibt es an Home Assistant weiter.

## Funktionen

- **Echte Rechnungen, automatisch.** Ladecockpit erkennt das Ladeende, holt die Rechnung innerhalb weniger Minuten und meldet sie genau einmal an Home Assistant. Ein Blueprint bucht sie in deine eigenen Helfer.
- **Preis-Radar.** Zeigt aus deinen eigenen Rechnungen, zu welcher Uhrzeit und an welchem Supercharger du am günstigsten lädst.
- **MultiPass.** Fremde Ladesäulen, die über Tesla MultiPass bezahlt werden, erkennt Ladecockpit in den Tesla-Rechnungen und weist sie getrennt aus, mit eigenem Ø-Preis. Eine Liste zeigt jede Drittanbieter-Station, an der MultiPass bei dir schon funktioniert hat – Anbieter, Ladungen, Ø-Preis, letzte Nutzung und Kartenlink –, damit du weißt, wo die Tesla-App angenommen wird.
- **Nächster Ladestopp.** Sagt anhand deines Verbrauchs voraus, wann der Akku die Untergrenze erreicht (Standard: 10 %), und wann und wo du vorher am günstigsten lädst: die beste Kombination aus Supercharger und Uhrzeit aus deinen eigenen Rechnungen.
- **Monatsübersicht.** Kosten, kWh, Ø-Preis, Kosten pro 100 km/mi, optional Vergleich mit einem Referenzpreis oder den Spritkosten eines zweiten Autos.
- **Ersparnis ggü. Verbrenner.** Was dieselbe Strecke mit Benzin oder Diesel gekostet hätte (feste Werte oder live aus Home Assistant, z. B. ein Spritpreis-Sensor), pro Monat und aufs Jahr hochgerechnet.
- **Monatsbericht.** Am Monatsersten eine Zusammenfassung des Vormonats als Event und Benachrichtigung in Home Assistant.
- **Tesla-Gutschriften richtig verbucht.** Ladungen, die teilweise mit Tesla-Gutschriften bezahlt wurden (z. B. Gratis-Supercharging zum Neuwagen), zeigen Gezahltes, Listenpreis und Gutschrift. Preisvergleiche nutzen den Listenpreis, eine Gutschrift lässt also keinen Supercharger billig aussehen.
- **Laden zu Hause.** Mit dem Energiezähler deiner Wallbox und deinem Strompreis (auch dynamische Tarife) fließt das Laden zu Hause in Kosten pro 100 km/mi und Ersparnis ein.
- **Akku-Gesundheit.** Reichweite bei 100 % im Zeitverlauf, aus den Messwerten, die Ladecockpit ohnehin speichert, dazu der Supercharger-Anteil.
- **Verbrauch nach Außentemperatur.** Wie viel mehr Akku das Auto bei Kälte braucht.
- **Monats-PDF.** Deckblatt mit allen Ladungen (netto, MwSt., brutto, Gutschriften) plus alle Rechnungen eines Monats in einer PDF – für Steuer oder Arbeitgeber.
- **Ladeleistung und Verbrauch.** Ø kW pro Ladung und pro Supercharger, kWh pro 100 km/mi inklusive Ladeverlusten.
- **Langsame Ladungen erkannt.** Hat eine Ladung deutlich weniger Leistung bekommen als sonst an diesem Supercharger, wird sie markiert, mit dem üblichen Wert und den häufigen Gründen (kalter Akku, geteilte oder gedrosselte Säule).
- **Abgleich.** Vergleicht deine Summen in Home Assistant mit den Rechnungen.
- **Export.** Alle Ladungen als CSV, alle Rechnungen eines Monats als ein ZIP.
- **Problem-Meldung.** Benachrichtigung in Home Assistant, wenn die Tesla-Anmeldung abläuft oder der Abgleich wiederholt fehlschlägt.
- **Sensoren fürs Dashboard.** Nächster Ladestopp, Akku, Monatskosten, letzte Ladung und Preistipp als Entitäten in Home Assistant, dazu eine fertige Dashboard-Sektion.
- **Live beim Laden.** Während das Auto lädt, zeigt die Web-App die Leistung in kW, wann das Ladelimit erreicht ist und einen Countdown dorthin, und folgt dem Akku alle 15 Sekunden.
- **Zwei Designs.** *Klassisch*, ruhig und nah an der App des Autos, oder *Dynamisch*, ein Cockpit bei Nacht: der Akku als leuchtender Ring, durch den beim Laden Energie fließt, Licht, das dem Akku und der Tageszeit folgt, Zahlen, die hochzählen, und ein Preis-Radar, das das aktuelle Zeitfenster markiert.
- **Dein Auto, wie es aussieht.** Ein Bild deines Teslas aus Teslas eigenem Konfigurator, für jedes Model S, 3, X, Y und den Cybertruck: Generation, Ausstattung, Farbe, Felgen und Ansicht in der Web-App wählen (das Modell wird aus der FIN erkannt). Das Bild geht als `sensor.ladecockpit_car` auch an Home Assistant.
- **Funktioniert auch offline.** Speichert einen eigenen Verlauf von Akkustand und Kilometerstand, z. B. für ein Auto in der Tiefgarage ohne Empfang.
- **Sparsam bei der Tesla-API.** Live-Daten kommen aus Home Assistant. Tesla wird nur nach der Ladehistorie gefragt, etwa 150–200 Abfragen im Monat (≈ 0,40 $).
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
| `HA_ENT_CHARGING` | `sensor.my_tesla_charging` | Rechnung direkt nach dem Ladeende; Live-Ansicht beim Laden |
| `HA_ENT_CHARGE_POWER`, `HA_ENT_TIME_TO_FULL` | `sensor.my_tesla_charger_power`, `sensor.my_tesla_time_to_full_charge` | kW und Uhrzeit, wann das Ladelimit erreicht ist, beim Laden |
| `HA_ENT_FUEL_CONSUMPTION` / `FUEL_CONSUMPTION`, `HA_ENT_FUEL_PRICE` / `FUEL_PRICE` | `7.5`, `sensor.spritpreis` | Ersparnis ggü. Verbrenner |
| `HA_ENT_FUEL_COST_TOTAL`, `HA_ENT_FUEL_LITRES_TOTAL` | `input_number.tankkosten_gesamt`, `input_number.tankliter_gesamt` | der wirklich bezahlte Literpreis (Ø der letzten 90 Tage) statt des Spritpreises; beide Summen steigen bei jedem Tanken |
| `HA_ENT_HOME_ENERGY`, `HA_ENT_HOME_PRICE` / `HOME_PRICE` | `sensor.wall_connector_energy`, `0.32` | Laden zu Hause |
| `HA_ENT_OUTSIDE_TEMP` | `weather.home` | Verbrauch nach Temperatur |

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

3. Daraus eine Automation erstellen und die Helfer auswählen. Unter *Additional actions* kannst du z. B. eine Benachrichtigung ergänzen. Dort stehen die Variablen `site`, `kwh`, `total`, `price_per_kwh`, `idle_fee`, `currency`, `network`, `avg_power_kw`, `typical_power_kw`, `slow` und `text` zur Verfügung. `slow` ist `true`, wenn die Ladung weniger als 60 % der Leistung bekam, die du an dieser Station sonst bekommst.
4. `HA_ENT_COST_TOTAL` und `HA_ENT_KWH_TOTAL` auf die beiden Helfer setzen, dann zeigt die App den Abgleich.

Optional: [`homeassistant/ladecockpit_package.yaml`](homeassistant/ladecockpit_package.yaml) bringt einen `rest_command`, um die Rechnungssuche selbst anzustoßen.

### 6. Sensoren und Dashboard

Ladecockpit legt diese Entitäten in Home Assistant selbst an (abschaltbar mit der App-Option `publish_entities` bzw. `PUBLISH_ENTITIES=false`):

| Entität | Zustand | Nützliche Attribute |
|---|---|---|
| `sensor.ladecockpit_next_charge` | Datum des nächsten Ladestopps | `text`, `days`, `plan` (wann und wo laden), `plan_saving` |
| `sensor.ladecockpit_battery` | Akkustand in %, bei Funkstille der letzte bekannte Wert | `range`, `last_known`, `as_of` |
| `sensor.ladecockpit_month_cost` | Ladekosten im laufenden Monat | `energy_kwh`, `price_per_kwh`, `cost_per_100`, `kwh_per_100`, `multipass_cost`, `savings`, `projected_year_cost`, `previous_cost` |
| `sensor.ladecockpit_last_charge` | Kosten der letzten Ladung | `network`, `site`, `energy_kwh`, `price_per_kwh`, `avg_power_kw`, `typical_power_kw`, `slow`, `start_soc`, `text` |
| `sensor.ladecockpit_price_tip` | deine günstigste Uhrzeit als Satz | `best_time`, `best_site`, `insights` |
| `sensor.ladecockpit_range_at_100` | Reichweite bei 100 % (Langzeitstatistik) | `change_pct`, `since`, `supercharger_share` |
| `sensor.ladecockpit_consumption` | abgerechnete kWh pro 100 km/mi diesen Monat | `by_temperature`, `temperature_tip` |
| `sensor.ladecockpit_car` | Name des Autos, z. B. `Model 3 Performance`; sein Bild ist das Entitätsbild | `image`, `image_front`, `image_side`, `image_rear`, `model`, `trim`, `paint`, `wheels` |
| `sensor.ladecockpit_multipass` | Anzahl der Drittanbieter-Stationen, an denen MultiPass funktioniert hat | `text`, `stations` (Standort, Anbieter, Ladungen, Ø-Preis, letzte Nutzung, `map_url`), `operators`, `sessions`, `price_per_kwh` |
| `binary_sensor.ladecockpit_problem` | `on`, wenn die Tesla-Anmeldung abgelaufen ist, der Abgleich fehlschlägt oder eine Entität fehlt | `kind`, `message`, `last_sync` |

Sie werden über die REST-API geschrieben und haben keine eindeutige ID, lassen sich also nicht in der Oberfläche umbenennen. Nach einem Neustart von Home Assistant sind sie nach wenigen Minuten wieder da. Eine fertige Dashboard-Sektion steht in [`homeassistant/dashboard_card.yaml`](homeassistant/dashboard_card.yaml).

### Bild deines Autos

Oben in der Web-App steht dein Tesla. Ohne eigene Auswahl errät Ladecockpit Modell und Generation aus der FIN in der Ladehistorie (oder `TESLA_VIN`). Über **Anpassen** wählst du Modell und Generation, Ausstattung, Felgen, Farbe und Ansicht – Model S, 3, X und Y aller Generationen seit 2012 und den Cybertruck. Angeboten werden nur Kombinationen, die Teslas Konfigurator darstellen kann, das Bild ist also nie halb leer. Die Auswahl wird in Ladecockpit gespeichert, nicht im Auto: Es ist nur ein Bild.

Die Bilder lädt dein Browser direkt von Teslas Bildserver (`static-assets.tesla.com`). Sie kosten keine Fleet-API-Abfragen. In Home Assistant trägt `sensor.ladecockpit_car` das Bild als Entitätsbild (Kachel-Karten mit `show_entity_picture: true`) und als Attribut je Ansicht, z. B. für eine Markdown-Karte:

```yaml
type: markdown
text_only: true
content: >-
  <img src="{{ state_attr('sensor.ladecockpit_car', 'image') }}" width="100%">
```

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

**Wo MultiPass schon funktioniert hat.** Aus den Rechnungen listet Ladecockpit jede Drittanbieter-Station mit mindestens einer MultiPass-Ladung: den Anbieter (wenn der Standortname ihn nennt), Anzahl der Ladungen, Ø-Preis, das letzte Mal und einen Link, der die Station in Google Maps sucht. Die Anbieter stehen als Chips darüber, so siehst du auf einen Blick, welche Netze MultiPass bei dir schon angenommen haben. Neueste zuerst. Das sortiert nur Rechnungen um, die schon da sind – keine zusätzlichen Tesla-Abfragen. Es ist ein Protokoll deiner eigenen Ladungen, kein Verzeichnis: Ob eine Station, an der du noch nicht warst, MultiPass annimmt, zeigen die Tesla-App und die Karte im Auto, wenn Drittanbieter-Ladestationen eingeblendet sind. In Home Assistant steht dieselbe Liste in `sensor.ladecockpit_multipass`, z. B. für eine Markdown-Karte:

```yaml
type: markdown
content: |
  {% for s in state_attr('sensor.ladecockpit_multipass', 'stations') or [] %}
  - [{{ s.site }}]({{ s.map_url }}) · {{ s.sessions }}× · zuletzt {{ s.last_label }}
  {% else %}
  {{ state_attr('sensor.ladecockpit_multipass', 'text') }}
  {% endfor %}
```

Wird eine MultiPass-Ladung als Supercharger angezeigt (oder umgekehrt), bitte ein Issue mit der anonymisierten Ausgabe von `/api/debug/raw` für diese Ladung aufmachen. Im Log steht außerdem, welche Felder Ladecockpit noch nicht kennt.

## Kosten

Die Fleet API wird pro Abfrage abgerechnet. Ladecockpit nutzt nur Datenabfragen für Ladehistorie und Rechnungen. Mit den Standardeinstellungen sind das etwa 150–200 Abfragen im Monat: ein Abgleich alle 6 Stunden plus ein paar Abfragen nach jeder Ladung (≈ 0,40 $ bei 0,002 $ pro Abfrage), weit innerhalb des monatlichen Guthabens von 10 $, das Tesla jedem Entwicklerkonto gibt. `API_BUDGET_REQUESTS` (Standard 1500) ist eine harte Obergrenze. Die App zeigt den Zählerstand des laufenden Monats.

## Datenschutz und Sicherheit

- Die Web-App lädt nichts von anderen Diensten nach, außer dem Bild deines Autos aus Teslas Konfigurator; die Schriften bringt sie selbst mit. Ganz unten auf der Seite wählst du das Design: klassisch (ruhig, nah an der App des Autos) oder dynamisch (ein Cockpit bei Nacht, das sich bewegt und dem Akku folgt).
- Alles bleibt bei dir: Tokens, Rechnungen und Messwerte liegen im Docker-Volume `ladecockpit-data` (SQLite und PDF-Cache).
- Ladecockpit spricht nur mit Tesla und deinem Home Assistant. Die Web-App lädt außerdem das Bild deines Autos von Teslas Bildserver. Die Kartenlinks der MultiPass-Stationen öffnen eine Google-Maps-Suche nach dem Stationsnamen – nur wenn du einen anklickst.
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
