# Ladecockpit – Produkt- und Architekturentscheidung

Stand: 2026-11-07

## Produktziel

Ladecockpit ist eine **kostenlose App für private Tesla-Fahrer**. Es gibt keine Geschäftskunden-, Flotten- oder kommerzielle Lizenzvariante. Die App soll ohne Home Assistant funktionieren.

Das Projekt selbst soll keine laufenden Kosten verursachen: kein vom Projekt betriebener Cloud-Dienst, kein zentraler Benutzerkonten-Dienst, kein kostenpflichtiger Datenbankdienst und keine verpflichtenden Drittanbieter-Abonnements.

## Verbindliche Leitplanken

1. **Self-hosted als Standard:** Nutzer betreiben Ladecockpit selbst, vorzugsweise per Docker auf einem vorhandenen NAS, Mini-PC, Homeserver oder Raspberry Pi.
2. **Home Assistant ist optional:** Die Tesla-Ladehistorie und Rechnungen werden direkt über die Tesla Fleet API bezogen. HA ergänzt Live-Daten und Automationen, ist aber keine Voraussetzung.
3. **Daten bleiben lokal:** Datenbank, OAuth-Tokens, Rechnungs-PDFs und Exporte verbleiben auf dem Gerät des Nutzers.
4. **Keine zentrale Cloud-Abhängigkeit:** Registrierung, zentrale Benutzerverwaltung, zentrales Hosting und Cloud-Synchronisierung gehören nicht zum geplanten Produkt.
5. **Keine versteckten Kosten:** Keine kostenpflichtigen APIs oder Dienste als zwingende Voraussetzung. Mögliche Kosten externer Anbieter müssen vor der Einrichtung klar benannt werden.
6. **Bestehende Installationen schützen:** Die Home-Assistant-App und die funktionierende Version 0.12.2 bleiben kompatibel. Änderungen werden schrittweise und rückwärtskompatibel umgesetzt.

## Wichtige Kostenabgrenzung

Ladecockpit kann selbst kostenlos und lokal betrieben werden. Die Tesla Fleet API unterliegt jedoch Teslas eigenen Bedingungen und möglichen nutzungsabhängigen Gebühren. Das Projekt kann deshalb keine garantierten Nullkosten für Tesla-API-Nutzung versprechen.

Daraus folgen technische Anforderungen:

- API-Aufrufe minimieren und vorhandene Daten lokal wiederverwenden.
- Keine unnötigen Fahrzeug-Weckvorgänge oder Steuerbefehle.
- API-Budget und Synchronisationsintervalle konfigurierbar machen.
- Vor einer Überschreitung des konfigurierten Budgets die Synchronisierung pausieren oder deutlich warnen.
- In der Einrichtung transparent erklären, welche Tesla-Entwicklerregistrierung und mögliche externe Kosten anfallen.
- Keine kostenpflichtigen Zusatzdienste voraussetzen.

## Zielarchitektur

```text
                         optional
Home Assistant  <--------------------------+
      |                                     |
      | Live-Daten / Events                 |
      v                                     |
+-------------------------------------------+------+
|                 Ladecockpit                      |
|                                                   |
|  Web-App / PWA  |  Tesla OAuth  |  Sync-Service   |
|                 |               |                 |
|  lokale SQLite-Datenbank + Rechnungs-PDFs         |
+-------------------------+-------------------------+
                          |
                          v
                  Tesla Fleet API
```

- Docker ist der universelle Installationsweg.
- Die Home-Assistant-App bleibt ein zusätzlicher Installationsweg.
- Die Weboberfläche wird für Smartphone und Desktop optimiert und kann als PWA installiert werden.
- Ein späterer nativer Mobile-Client ist optional und greift auf die selbst gehostete Instanz des Nutzers zu.
- Es gibt keine mandantenfähige SaaS-Architektur und keine zentrale Speicherung privater Fahrzeugdaten.

## Geplante Umsetzung in Etappen

### Phase 1 – Eigenständigen Betrieb vervollständigen

- Docker-Installation als gleichwertigen, dokumentierten Standard etablieren.
- Einrichtungsablauf für Tesla ohne Home Assistant prüfen und vereinfachen.
- HA-Funktionen sichtbar als optional kennzeichnen.
- Dashboard ohne HA-Daten sinnvoll nutzbar machen.
- Web-Einrichtungsseite für Status, Tesla-Verbindung und optionale HA-Verbindung vorbereiten.
- Sicherheitsanforderungen für extern erreichbare Installationen dokumentieren.

### Phase 2 – Web-Einrichtungsassistent

- Statusprüfung für Tesla-Konfiguration und OAuth-Verbindung.
- Verständliche Schritt-für-Schritt-Anleitung zur Tesla Developer App.
- OAuth-Verbindung und Rückmeldung bei abgelaufener Anmeldung.
- Optionaler HA-Verbindungsassistent mit Prüfung der URL und des Tokens.
- Konfiguration ohne manuelle Bearbeitung mehrerer Dateien ermöglichen, soweit sicher möglich.
- Secrets niemals im Klartext in Logs oder API-Antworten ausgeben.

### Phase 3 – API- und Betriebskosten minimieren

- Synchronisierung nur bei Bedarf und mit lokalem Cache.
- Konfigurierbare API-Budgets und nachvollziehbare Verbrauchsanzeige.
- Backoff bei Fehlern und Rate Limits.
- Keine Fahrzeugsteuerung, kein Wake-up und keine unnötigen Live-Abfragen.
- Datenexport und vollständige lokale Datensicherung bereitstellen.

### Phase 4 – Mobile Nutzung

- Zuerst die responsive Web-App/PWA vervollständigen.
- Danach den vorhandenen Flutter-Ansatz gegen die stabile lokale API integrieren.
- Die mobile App verbindet sich mit der eigenen Ladecockpit-Instanz des Nutzers; kein zentraler Cloud-Account wird benötigt.

## Nicht-Ziele

- Kein kostenpflichtiges Abo und keine Werbung.
- Kein zentraler Cloud- oder SaaS-Betrieb durch das Projekt.
- Keine Geschäftskunden-, Flotten- oder Händlerfunktionen.
- Keine verpflichtende Home-Assistant-Installation.
- Keine Fahrzeugsteuerung oder Fernbedienung des Tesla.

## Akzeptanzkriterien

Eine private Person kann Ladecockpit auf einem vorhandenen Gerät per Docker starten, die Tesla-Verbindung einrichten und Ladehistorie sowie Rechnungen nutzen, ohne Home Assistant und ohne einen von Ladecockpit betriebenen Cloud-Dienst.

Optionale HA-Funktionen dürfen fehlen, ohne dass Kernfunktionen wie Rechnungen, Ladehistorie, Auswertungen, PDF-Ansicht und Export ausfallen.

## Schutz der bestehenden Version

- Keine Änderung oder Bereitstellung auf einer produktiven Home-Assistant-Installation ohne gesonderte ausdrückliche Freigabe.
- Keine Zusammenführung oder Veröffentlichung von Pull Requests ohne Freigabe.
- Bestehende Datenbankinhalte, Rechnungen und PDFs dürfen durch Migrationen oder Updates nicht verloren gehen.
