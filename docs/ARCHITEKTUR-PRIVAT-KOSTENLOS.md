# Ladecockpit – Produkt- und Architekturentscheidung

Stand: 2026-11-07

## Produktziel

Ladecockpit erhält zwei klar getrennte Zielgruppen und Angebotsmodelle:

- **Privatnutzer:** Ladecockpit bleibt dauerhaft kostenlos. Der private Betrieb erfolgt lokal/self-hosted, ohne verpflichtendes Konto, Abo oder zentrale Cloud.
- **Geschäftskunden:** Für Unternehmen kann später eine kostenpflichtige Business-Edition angeboten werden, vorzugsweise self-hosted oder hybrid. Denkbare Bestandteile sind kommerzielle Nutzungsrechte, erweiterte Verwaltungsfunktionen, Mehrbenutzer-/Flottenfunktionen, zentrale Richtlinien, Integrationen und optional Support bzw. Wartung.

Die private kostenlose Version ist das Kernprodukt und darf nicht durch die Business-Edition eingeschränkt werden. Geschäftskundenfunktionen werden separat geplant und dürfen die private Nutzung nicht künstlich begrenzen.

Das Projekt soll für private Nutzer keine laufenden Hostingkosten verursachen: kein vom Projekt betriebener Cloud-Dienst, kein zentraler Benutzerkonten-Dienst, kein kostenpflichtiger Datenbankdienst und keine verpflichtenden Drittanbieter-Abonnements.

## Verbindliche Leitplanken

1. **Privat dauerhaft kostenlos:** Kernfunktionen wie Tesla-Verbindung, Ladehistorie, Rechnungen, Auswertungen, PDF-Ansicht und Export bleiben für private Nutzer kostenlos.
2. **Self-hosted als Standard:** Nutzer betreiben Ladecockpit selbst, vorzugsweise per Docker auf einem vorhandenen NAS, Mini-PC, Homeserver oder Raspberry Pi.
3. **Home Assistant ist optional:** Die Tesla-Ladehistorie und Rechnungen werden direkt über die Tesla Fleet API bezogen. HA ergänzt Live-Daten und Automationen, ist aber keine Voraussetzung.
4. **Daten bleiben lokal:** Datenbank, OAuth-Tokens, Rechnungs-PDFs und Exporte verbleiben standardmäßig auf dem Gerät des Nutzers.
5. **Keine zentrale Cloud-Abhängigkeit für Privatnutzer:** Registrierung, zentrale Benutzerverwaltung, zentrales Hosting und Cloud-Synchronisierung sind keine Voraussetzung für die kostenlose Edition.
6. **Business-Angebot separat:** Eine spätere Business-Edition kann kostenpflichtig sein und zusätzliche Funktionen, kommerzielle Nutzungsrechte, Support oder Wartung enthalten. Sie darf keine künstliche Paywall in private Kernfunktionen einführen.
7. **Erweiterbarkeit ohne Überbau:** Die Architektur soll spätere getrennte Editionen ermöglichen, aber jetzt keine unnötige Mandanten-, Abrechnungs- oder SaaS-Infrastruktur erhalten.
8. **Bestehende Installationen schützen:** Die Home-Assistant-App und die funktionierende Version 0.12.2 bleiben kompatibel. Änderungen werden schrittweise und rückwärtskompatibel umgesetzt.

## Wichtige Kostenabgrenzung

Ladecockpit selbst kann für Privatnutzer kostenlos und lokal betrieben werden. Die Tesla Fleet API unterliegt jedoch Teslas eigenen Bedingungen und möglichen nutzungsabhängigen Gebühren. Das Projekt kann deshalb keine garantierten Nullkosten für externe Tesla-API-Nutzung versprechen.

Daraus folgen technische Anforderungen:

- API-Aufrufe minimieren und vorhandene Daten lokal wiederverwenden.
- Keine unnötigen Fahrzeug-Weckvorgänge oder Steuerbefehle.
- API-Budget und Synchronisationsintervalle konfigurierbar machen.
- Vor einer Überschreitung des konfigurierten Budgets die Synchronisierung pausieren oder deutlich warnen.
- In der Einrichtung transparent erklären, welche Tesla-Entwicklerregistrierung und mögliche externe Kosten anfallen.
- Keine kostenpflichtigen Zusatzdienste für private Nutzer voraussetzen.

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

Private Edition: lokal, kostenlos, ohne Cloud-Konto
Business Edition (später): getrenntes Lizenz-/Funktionspaket,
self-hosted oder hybrid, nur bei konkretem Bedarf
```

- Docker ist der universelle Installationsweg.
- Die Home-Assistant-App bleibt ein zusätzlicher Installationsweg.
- Die Weboberfläche wird für Smartphone und Desktop optimiert und kann als PWA installiert werden.
- Ein späterer nativer Mobile-Client ist optional und greift auf die selbst gehostete Instanz des Nutzers zu.
- Die private Edition benötigt keine mandantenfähige SaaS-Architektur und keine zentrale Speicherung privater Fahrzeugdaten.
- Gemeinsame Kernkomponenten sollen möglichst identisch bleiben. Business-spezifische Funktionen werden sauber getrennt und optional aktiviert.

## Geplante Umsetzung in Etappen

### Phase 1 – Eigenständigen Privatbetrieb vervollständigen

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

### Phase 5 – Business-Edition evaluieren (später, getrennt)

Erst wenn die private Edition stabil ist, wird geprüft, ob ein ausreichend konkreter Bedarf bei Geschäftskunden besteht. Mögliche kostenpflichtige Bestandteile:

- Mehrere Fahrzeuge und Nutzer mit Rollen/Rechten.
- Flottenübersicht und gemeinsame Auswertungen.
- Zentrale Administration und Richtlinien.
- Erweiterte Exporte, Schnittstellen und Integrationen.
- Self-hosted- oder Hybrid-Betrieb.
- Kommerzielle Lizenz, Installationshilfe, Wartung und Support.

Vor Umsetzung sind Zielgruppe, Zahlungsbereitschaft, Lizenzmodell, Datenschutz, Supportaufwand und tatsächliche Zusatzkosten zu prüfen. Die Business-Edition darf keine kostenpflichtige Cloud voraussetzen, wenn ein self-hosted Modell den Bedarf erfüllt.

## Nicht-Ziele der privaten Edition

- Kein kostenpflichtiges Abo und keine Werbung.
- Kein zentraler Cloud- oder SaaS-Betrieb als Voraussetzung.
- Keine verpflichtende Home-Assistant-Installation.
- Keine Fahrzeugsteuerung oder Fernbedienung des Tesla.
- Keine künstliche Beschränkung privater Kernfunktionen zur Verkaufsförderung der Business-Edition.

## Akzeptanzkriterien

Eine private Person kann Ladecockpit auf einem vorhandenen Gerät per Docker starten, die Tesla-Verbindung einrichten und Ladehistorie sowie Rechnungen nutzen, ohne Home Assistant und ohne einen von Ladecockpit betriebenen Cloud-Dienst. Die privaten Kernfunktionen bleiben kostenlos.

Eine spätere Business-Edition kann separat lizenziert und kostenpflichtig angeboten werden, ohne die private Edition zu beschneiden.

Optionale HA-Funktionen dürfen fehlen, ohne dass Kernfunktionen wie Rechnungen, Ladehistorie, Auswertungen, PDF-Ansicht und Export ausfallen.

## Schutz der bestehenden Version

- Keine Änderung oder Bereitstellung auf einer produktiven Home-Assistant-Installation ohne gesonderte ausdrückliche Freigabe.
- Keine Zusammenführung oder Veröffentlichung von Pull Requests ohne Freigabe.
- Bestehende Datenbankinhalte, Rechnungen und PDFs dürfen durch Migrationen oder Updates nicht verloren gehen.
