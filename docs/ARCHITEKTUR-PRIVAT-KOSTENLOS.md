# Ladecockpit – Produkt- und Architekturentscheidung

Stand: 2026-11-11

## Produktziel

Ladecockpit ist ein freies Community-Projekt für alle Tesla-Fahrer: kostenlos, quelloffen (MIT) und nicht kommerziell. Es gibt keinen Kaufpreis, kein Abo, keine Werbung und keine kostenpflichtige Edition. Der Betrieb erfolgt lokal/self-hosted, ohne verpflichtendes Konto und ohne zentrale Cloud.

Das Projekt soll für Nutzer keine laufenden Hostingkosten verursachen: kein vom Projekt betriebener Cloud-Dienst, kein zentraler Benutzerkonten-Dienst, kein kostenpflichtiger Datenbankdienst und keine verpflichtenden Drittanbieter-Abonnements.

## Verbindliche Leitplanken

1. **Dauerhaft kostenlos:** Alle Funktionen wie Tesla-Verbindung, Ladehistorie, Rechnungen, Auswertungen, PDF-Ansicht und Export sind und bleiben kostenlos.
2. **Self-hosted als Standard:** Nutzer betreiben Ladecockpit selbst, vorzugsweise per Docker auf einem vorhandenen NAS, Mini-PC, Homeserver oder Raspberry Pi.
3. **Home Assistant ist optional:** Die Tesla-Ladehistorie und Rechnungen werden direkt über die Tesla Fleet API bezogen. HA ergänzt Live-Daten und Automationen, ist aber keine Voraussetzung.
4. **Daten bleiben lokal:** Datenbank, OAuth-Tokens, Rechnungs-PDFs und Exporte verbleiben standardmäßig auf dem Gerät des Nutzers.
5. **Keine zentrale Cloud-Abhängigkeit:** Registrierung, zentrale Benutzerverwaltung, zentrales Hosting und Cloud-Synchronisierung sind keine Voraussetzung.
6. **Allgemein für alle:** Keine Funktionen oder Voreinstellungen, die nur für eine bestimmte Installation passen. Was im Repository steht, muss für jeden Tesla-Fahrer funktionieren.
7. **Erweiterbarkeit ohne Überbau:** Keine Mandanten-, Abrechnungs- oder SaaS-Infrastruktur.
8. **Bestehende Installationen schützen:** Die Home-Assistant-App und bestehende Installationen bleiben kompatibel. Änderungen werden schrittweise und rückwärtskompatibel umgesetzt.

## Wichtige Kostenabgrenzung

Ladecockpit selbst ist kostenlos und läuft lokal. Die Tesla Fleet API unterliegt jedoch Teslas eigenen Bedingungen und möglichen nutzungsabhängigen Gebühren. Tesla gewährt privaten Konten derzeit ein monatliches Guthaben, das den Bedarf von Ladecockpit üblicherweise abdeckt; garantierte Nullkosten für die externe Tesla-API-Nutzung kann das Projekt trotzdem nicht versprechen.

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

Lokal, kostenlos, ohne Cloud-Konto
```

- Docker ist der universelle Installationsweg.
- Die Home-Assistant-App bleibt ein zusätzlicher Installationsweg.
- Die Weboberfläche wird für Smartphone und Desktop optimiert und kann als PWA installiert werden.
- Ein nativer Mobile-Client ist optional und greift auf die selbst gehostete Instanz des Nutzers zu.
- Ladecockpit benötigt keine mandantenfähige SaaS-Architektur und keine zentrale Speicherung privater Fahrzeugdaten.

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

- Kein Kaufpreis, kein kostenpflichtiges Abo, keine Werbung und keine kostenpflichtige Edition.
- Kein zentraler Cloud- oder SaaS-Betrieb als Voraussetzung.
- Keine verpflichtende Home-Assistant-Installation.
- Keine Fahrzeugsteuerung oder Fernbedienung des Tesla.

## Akzeptanzkriterien

Eine Person kann Ladecockpit auf einem vorhandenen Gerät per Docker starten, die Tesla-Verbindung einrichten und Ladehistorie sowie Rechnungen nutzen, ohne Home Assistant und ohne einen von Ladecockpit betriebenen Cloud-Dienst. Alle Funktionen bleiben kostenlos.

Optionale HA-Funktionen dürfen fehlen, ohne dass Kernfunktionen wie Rechnungen, Ladehistorie, Auswertungen, PDF-Ansicht und Export ausfallen.

## Schutz der bestehenden Version

- Keine Änderung oder Bereitstellung auf einer produktiven Home-Assistant-Installation ohne gesonderte ausdrückliche Freigabe.
- Keine Zusammenführung oder Veröffentlichung von Pull Requests ohne Freigabe.
- Bestehende Datenbankinhalte, Rechnungen und PDFs dürfen durch Migrationen oder Updates nicht verloren gehen.
