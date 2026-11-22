# Ladecockpit Mobil – Design-System im Fahrzeugstil

Stand: freigegebene Gestaltung (2026-11-08)

Das am 2026-11-08 freigegebene Bildschirmfoto des Ladecockpit-Dashboards in Home Assistant ist die gestalterische Vorlage für die Handy-App. Dieses Dokument übersetzt diese Richtung in Regeln für die Umsetzung. Es ersetzt kein Produktverhalten und entfernt keine vorhandenen Funktionen.

## Grundsätze

- Anmutung eines Kombiinstruments im Auto: ruhig, präzise, hochwertig und sofort lesbar.
- Dunkle Oberfläche zuerst, mit tiefen, fast schwarzen Flächen und zurückhaltenden Akzenten in Smaragd und Petrol.
- Fahrzeug und Akkustand stehen im Mittelpunkt; weitere Auswertungen bleiben leicht zu überblicken.
- Klare deutsche Beschriftungen, ausdrückliche Zeitstempel und ehrliche Angaben zu Aktualität und Offline-Zustand.
- Layouts zuerst fürs Handy, mit großzügigen Tippflächen und ohne seitliches Überlaufen.

## Grundfarben

| Wert | Farbe | Verwendung |
|---|---|---|
| Hintergrund | `#070B10` | Haupthintergrund der App |
| Fläche | `#111820` | Hauptkarten |
| Fläche erhöht | `#182329` | Verschachtelte Karten und Bedienelemente |
| Rahmen | `#27333A` | Dezente Kartenränder |
| Text primär | `#F2F6FA` | Hauptwerte und Überschriften |
| Text sekundär | `#8D9AAF` | Metadaten und ergänzende Beschriftungen |
| Akzent Grün | `#39E6A5` | Live, verbunden, positiver Zustand |
| Akzent Petrol | `#22C9C3` | Akkuanzeige und interaktive Hervorhebungen |
| Warnung | `#F5B85B` | Veraltete Daten oder Handlungsbedarf |
| Fehler | `#FF6B70` | Fehlgeschlagene Vorgänge und Verbindungsfehler |

## Form, Tiefe und Schrift

- Hauptkarten: Eckenradius 24–30 px, dezenter Rahmen von 1 px und zurückhaltender dunkler Verlauf.
- Nebenkarten: Eckenradius 16–20 px.
- Keine schweren Schatten und keine großen hellen Flächen; Leuchten ist Live- und aktiven Akzenten vorbehalten.
- Hauptwerte groß und möglichst mit Tabellenziffern; Metadaten bleiben gut lesbar.
- Abschnittsbeschriftungen in kompakten Großbuchstaben mit mäßigem Zeichenabstand.
- Abstände einheitlich in Schritten von 4 px; Innenabstand der Hauptkarten 20–24 px.

## Aufbau des Dashboards

1. Kopf mit App-Titel, Verbindungs- bzw. Live-Anzeige und einer klaren Aktualisieren-Aktion.
2. Fahrzeugkarte mit Name des Fahrzeugs, Modell und Ausstattung und dem Bild des Fahrzeugs, wenn ein gültiges Bild vorliegt.
3. Große Akkuanzeige als wichtigster Wert, mit Prozent und geschätzter Reichweite.
4. Ausdrückliche Angabe zur Aktualität der Daten (live, zuletzt bekannt, Zeitstempel) und zum Lade- bzw. Offline-Zustand.
5. Empfehlung bzw. Prognose für den nächsten Ladestopp.
6. Kennzahlen des Monats.
7. Letzte Ladung, Kostenentwicklung, Preis-Radar, Verlauf und Exporte.

## Verhalten von Anzeige und Status

- Die Akkuanzeige muss den tatsächlichen Ladestand zeigen; nie Beispielwerte zur Dekoration.
- Ladefenster oder eingestelltes Ziel sichtbar lassen, wenn die API es liefert.
- Live-Daten nutzen den grünen bzw. petrolfarbenen Akzent; zwischengespeicherte oder veraltete Daten die Warnfarbe und einen klaren Zeitstempel.
- Offline ist ein Zustand der Verbindung bzw. der Aktualität, kein Ersatz für den zuletzt bekannten Akkustand.
- Fehlende Werte bekommen einen neutralen Platzhalter; Reichweite oder Prozent nie erschließen.

## Vorhandene Funktionen bleiben erhalten

Die Neugestaltung betrifft nur die Darstellung, außer eine eigens geprüfte Änderung ist ausdrücklich nötig. Erhalten bleiben: Einrichtung der Verbindung, sichere Speicherung des Passworts, Zugriff über Tailscale, Aktualisieren, Status von Tesla und dem optionalen Home Assistant, Filter der Ladehistorie, Preis-Radar, Kostenentwicklung, Rechnungsansicht, Monatsberichte, CSV-Export und Teilen als ZIP.

## Barrierefreiheit und Anpassung an die Bildschirmgröße

- Starken Kontrast auf dunklen Flächen halten.
- Status nie allein über Farbe vermitteln; Farbe immer mit Text und/oder Symbol kombinieren.
- Tippflächen mindestens 44 px groß.
- Bei schmalen Bildschirmen Inhalte untereinander stapeln, statt Text zu stauchen oder Werte abzuschneiden.
- Die Schriftgröße des Systems beachten und keine Karten mit fester Höhe, in denen Text wachsen kann.

## Reihenfolge der Umsetzung

1. Zentrale Theme-Werte und gemeinsame Kartengestaltung einführen.
2. Fahrzeugkarte und Akkuanzeige an die freigegebene Vorlage anpassen.
3. Dieselben Regeln für Karten, Abstände und Schrift auf Auswertung, Verlauf und Exporte anwenden.
4. Zustände für Laden, leer, offline, veraltete Daten und Fehler prüfen.
5. Vor der Prüfung Flutter analyze, Widget-Tests und einen Android-Release-Build ausführen.

Kein Ausrollen in Produktion, keine Änderungen am laufenden Home Assistant, keine Änderungen an Zugangsdaten und kein Merge gehören zu dieser Grundlage.
