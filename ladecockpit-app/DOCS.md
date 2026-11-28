# Ladecockpit

Ladecockpit holt deine echten Supercharger-Rechnungen über die Tesla Fleet API und meldet jede neue als Event `ladecockpit_invoice` an Home Assistant. Die Web-App öffnest du über die Seitenleiste.

## Bevor du anfängst

- Du brauchst eine Tesla-Entwickler-App mit Zugriff auf die Fleet API. Nutzt du die Integration Tesla Fleet, kannst du deren App weiterverwenden.
- Trage in dieser App auf developer.tesla.com `http://localhost:8077/auth/callback` unter **Allowed Redirect URIs** ein und aktiviere den Scope **Vehicle Charging Management**.
- **Nur ein Ladecockpit betreiben.** Läuft es schon woanders (Docker auf einem PC oder Server), dort zuerst stoppen. Zwei Instanzen würden jede Rechnung doppelt melden.

## Konfiguration

1. **Tesla Client ID** und **Tesla Client Secret** eintragen.
2. Die Entitäten deines Autos eintragen. Alle sind optional, und jede schaltet eine Funktion frei:
   - **Entität Akkustand**, z. B. `sensor.my_tesla_battery_level`: Akku-Karte und Ladeprognose.
   - **Entität Reichweite**: steht neben dem Akkustand.
   - **Entität Kilometerstand**: Strecke sowie Kosten und kWh pro 100 km/mi.
   - **Entität Ladestatus**, z. B. `sensor.my_tesla_charging`: Die Rechnung wird gleich nach dem Ende einer Ladung abgerufen.
   - **Entität Ladeleistung** und **Entität Zeit bis voll**, z. B. `sensor.my_tesla_charger_power` und `sensor.my_tesla_time_to_full_charge`: Während das Auto lädt, zeigt die Web-App die Leistung und wann das Ladelimit erreicht ist.
3. Optional: die beiden `input_number`-Helfer, in die der Blueprint bucht. Sie schalten den Abgleich „HA gegen Rechnungen“ frei.
4. Die App starten und in der Seitenleiste **Ladecockpit** öffnen.

## Mit Tesla verbinden

1. **Bei Tesla anmelden** anklicken. Tesla öffnet sich in einem neuen Tab.
2. Nach der Anmeldung leitet Tesla auf `http://localhost:8077/auth/callback?code=…` weiter. Diese Seite lädt nicht, das ist so gewollt.
3. Die vollständige Adresse aus der Adresszeile dieses Tabs kopieren und in das Feld in Ladecockpit einfügen.

Der erste Abgleich startet sofort. Ältere Rechnungen werden nur übernommen und **nicht** gemeldet, damit Summen, die du schon führst, nicht doppelt gezählt werden.

## Rechnungen buchen

Den Blueprint `blueprints/automation/ladecockpit/book_invoice.yaml` aus dem Repository importieren. Er addiert jede Rechnung zu deinen Helfern und kann eine Benachrichtigung schicken. Willst du nur die Benachrichtigung, stattdessen oder zusätzlich `blueprints/automation/ladecockpit/notify_invoice.yaml` importieren; der braucht keine Helfer.

## Vergleich mit einem Verbrenner

Verbrauch (L/100 km) und Spritpreis eines Vergleichsautos eintragen, entweder als feste Werte oder als Entitäten (z. B. der Durchschnittsverbrauch deines anderen Autos und ein Spritpreis-Sensor). Ladecockpit zeigt dann, was dieselbe Strecke gekostet hätte und was du gespart hast, pro Monat und hochgerechnet aufs Jahr.

Mit *Spritpreis als Tagesdurchschnitt* (`FUEL_PRICE_DAILY`) wird die Strecke jedes Tages mit dem Tagesdurchschnitt der Spritpreis-Entität berechnet, z. B. dem günstigsten E10-Preis in deiner Nähe, der sich viele Male am Tag ändert. Der Vergleich zeigt dann den Durchschnitt über den Monat, gewichtet nach der Strecke jedes Tages.

## Günstig laden und der Referenzpreis

Viele Supercharger sind nachts und früh am Morgen günstiger. Sobald Ladecockpit an einem Standort beide Preise in deinen Rechnungen gesehen hat, zeigt die Monatskarte, was das Laden dort zur günstigen Zeit in diesem Monat gespart hat: diese Ladungen zum Tagespreis des Standorts, alle anderen zu ihrem eigenen Preis. Eine Preisänderung oder ein teurer Standort zählt nie als Ersparnis, und Gutschriften von Tesla bleiben außen vor.

Möchtest du lieber mit einem eigenen Preis vergleichen, z. B. dem, mit dem du die Kosten früher geschätzt hast, trag ihn unter *Entität Referenzpreis* oder *Referenzpreis pro kWh* ein. `0` schaltet den Vergleich ab.

## Benachrichtigungen aufs Handy ohne Home Assistant

Die App ntfy installieren (F-Droid, Google Play, App Store) und ein Thema mit langem, zufälligem Namen abonnieren, z. B. `ladecockpit-7f3k9q`. Die vollständige Adresse unter *Push aufs Handy (ntfy-Thema)* eintragen, z. B. `https://ntfy.sh/ladecockpit-7f3k9q`, oder die Adresse deines eigenen ntfy-Servers (mit Zugangstoken, falls er eines verlangt). Ladecockpit schickt dann jede neue Rechnung, Probleme mit der Tesla-Anmeldung oder dem Abgleich und den Monatsbericht. *Testnachricht senden* unter *Betrieb* in der Web-App prüft die Einrichtung. Auf ntfy.sh kann jeder die Nachrichten lesen, der den Namen des Themas kennt – sie enthalten Ort, kWh und Betrag einer Ladung, sonst nichts.

## Weitere Optionen

- **Laden zu Hause**: der Zähler deiner Wallbox (kWh, nur steigend) und dein Strompreis, fest oder aus einer Entität wie einem dynamischen Tarif. Verwendet wird der Preis zum Zeitpunkt des Ladens.
- **Außentemperatur**: ein Sensor oder eine Wetter-Entität, für den Verbrauch nach Temperatur.

## Datensicherung und Jahresübersicht

In der Web-App gibt es unter **Verbindungen & API-Kosten** die Knöpfe **Sicherung herunterladen** und **Sicherung einspielen**: Ladehistorie, Messwerte und Rechnungen in einer Datei, ohne die Tesla-Anmeldung. Das Einspielen ersetzt die Ladehistorie; Ladungen, die schon an Home Assistant gemeldet wurden, werden nicht doppelt gebucht. Nach einem Umzug auf ein anderes Home Assistant einmal bei Tesla anmelden.

Unter **Export** steht für jedes Jahr mit Ladungen eine **Jahresübersicht** als PDF: eine Zeile pro Monat mit Ladungen, kWh, netto, MwSt., brutto und Gutschriften.

## Sensoren

Ladecockpit legt eigene Entitäten an: `sensor.ladecockpit_next_charge`, `sensor.ladecockpit_battery`, `sensor.ladecockpit_month_cost`, `sensor.ladecockpit_month_energy` (kWh in diesem Monat, für das Energie-Dashboard), `sensor.ladecockpit_last_charge`, `sensor.ladecockpit_price_tip`, `sensor.ladecockpit_range_at_100`, `sensor.ladecockpit_consumption`, `sensor.ladecockpit_car` (ein Bild deines Autos, ausgewählt in der Web-App unter **Anpassen**), `sensor.ladecockpit_multipass` (Fremdstationen, an denen MultiPass bei dir funktioniert hat, mit Kartenlinks) und `binary_sensor.ladecockpit_problem`. Du kannst sie in Dashboards und Automationen nutzen. Einen fertigen Dashboard-Abschnitt findest du im Repository unter `homeassistant/dashboard_card.yaml`. Abschalten lässt sich das mit **Sensoren in Home Assistant anlegen**.

Monatskosten und Monatsenergie führen Langzeitstatistiken, mit einer neuen Summe in jedem Monat.

Diese Entitäten haben keine eindeutige ID. Man kann sie deshalb in der Oberfläche nicht umbenennen, und nach einem Neustart von Home Assistant fehlen sie ein paar Minuten. Die optionale **Ladecockpit-Integration** macht daraus echte Entitäten mit denselben IDs, einem Gerät und Wiederherstellung nach einem Neustart: im Marketplace (vor Home Assistant 2026.11 in HACS) `https://github.com/uekala/ladecockpit` als benutzerdefiniertes Repository hinzufügen (in HACS Typ *Integration*), *Ladecockpit* herunterladen, Home Assistant neu starten und die Integration unter *Einstellungen → Geräte & Dienste* hinzufügen. Die App findet sie innerhalb von fünf Minuten; einzustellen gibt es nichts.

## Probleme

Läuft die Tesla-Anmeldung ab oder schlägt der Abgleich wiederholt fehl, legt Ladecockpit eine Benachrichtigung in Home Assistant an und löst das Event `ladecockpit_problem` aus. Abschalten kannst du das mit **Bei Problemen benachrichtigen**.

## Netzwerkzugriff und Sicherheit

Die Seitenleiste nutzt Ingress von Home Assistant und wird von Home Assistant angemeldet. Der optionale Port `8077/tcp` umgeht Ingress; lass ihn abgeschaltet, solange du keinen direkten Zugriff brauchst, zum Beispiel für die [Handy-App](https://github.com/uekala/ladecockpit/blob/main/mobile/README.md). Der direkte Zugriff bleibt gesperrt, bis du ein **Mobiles App-Passwort** setzt: zuerst setzen, die App neu starten und erst dann den Port freigeben. Die Handy-App meldet sich mit diesem Passwort an. Beschränke den Port auf ein vertrauenswürdiges privates Netz oder ein VPN wie Tailscale, oder stell ihn hinter einen Reverse-Proxy, der Anmeldung und HTTPS verlangt. Gib ihn nicht direkt ins Internet frei. Die Pflicht zu `APP_PASSWORD` aus dem Standalone-Betrieb gilt nicht für die Home-Assistant-App, die nur über Ingress läuft.
