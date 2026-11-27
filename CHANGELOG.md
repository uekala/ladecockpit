# Changelog

## Unveröffentlicht

- **Winter gegen Sommer.** Neuer Bereich *Winterzeit und Sommerzeit* in der Web-App: Strecke, Verbrauch (kWh pro 100 km) und Kosten pro 100 km der letzten zwölf Monate, geteilt nach der Zeitumstellung der eingestellten Zeitzone (ohne Zeitumstellung April bis September als Sommer). Energie und Kosten kommen aus den Rechnungen plus Laden zu Hause, Ladeverluste zählen also mit. Eine Jahreszeit mit weniger als 300 km zeigt „Noch zu wenig Strecke“. Liegen beide vor und unterscheiden sie sich um mindestens 5 %, gibt es einen Tipp („In der Winterzeit braucht dein Tesla … – rund 25 % mehr Strom im Winter“). Neues Feld `seasons` im Dashboard-JSON; der Sensor `sensor.ladecockpit_consumption` hat neue Attribute `winter_kwh_per_100`, `summer_kwh_per_100`, `winter_cost_per_100`, `summer_cost_per_100`, `winter_distance`, `summer_distance`, `winter_price_per_kwh`, `summer_price_per_kwh`, `season_now`, `winter_more_kwh_pct`, `winter_more_cost_pct` und `season_tip`.
- Handy-App: Fehlermeldungen beim Teilen, Exportieren und bei Tipps sind verständlich formuliert statt roher Ausnahmetexte („Exception: …“); Netzwerkfehler klingen wie beim Laden des Cockpits.
- Handy-App: Die Zurück-Taste führt aus „Ladevorgänge“ und „Auswertung“ erst zum Cockpit, statt die App zu schließen.

## 0.23.4 – 2026-11-22

- **Ein Auto ohne Verbindung ist kein Einrichtungsproblem.** Schläft das Auto oder hat es keinen Empfang und Home Assistant startet neu, hat die Auto-Integration keine Werte, bis das Auto wieder online ist. Die Einrichtungsprüfung meldete dann Akkustand, Reichweite, Kilometerstand und Ladestatus als „gerade nicht verfügbar“ und bat, die Einrichtung zu prüfen. Wenn jetzt jede Entität des Autos existiert, aber keinen Wert hat, und Ladecockpit schon Werte des Autos gespeichert hat, sagt die Einrichtungsprüfung „Auto offline – Werte vom letzten Stand 21.11. 21:12“ und zeigt keine Warnung. Eine einzelne Entität ohne Wert bei verbundenem Auto, eine Entität, die es nicht gibt, und ein Auto, das noch nie einen Wert geliefert hat, werden weiter markiert. Neues Feld `offline` in `setup.checks` (Zeitpunkt des letzten Stands), `offline` je Entität.
- **Tipps lassen sich ausblenden.** Einen Tipp der Einrichtungsprüfung („Lädst du auch zu Hause? …“) blendest du in der Web-App und in der Handy-App mit × aus; *Ausgeblendete Tipps wieder zeigen* holt sie zurück. Eine halb eingerichtete Funktion (z. B. ein Verbrenner-Vergleich ohne Spritpreis) bleibt stehen, bis sie behoben ist. Ausgeblendete Tipps werden auf dem Server gespeichert und kommen mit in die Datensicherung. API: `PUT /api/hint` (`{"id": "no_home", "hidden": true}`), `DELETE /api/hints/hidden`; neue Felder `dismissable` je Hinweis und `hidden` (Zahl der ausgeblendeten Tipps) in `setup.checks`.
- Handy-App: Das Cockpit sagt „Auto offline“ statt eines orangen „Ladestatus nicht verfügbar“, solange es die letzten bekannten Werte zeigt; × neben jedem Tipp und *Ausgeblendete Tipps wieder zeigen* in der Einrichtungsprüfung.

## 0.23.3 – 2026-11-21

- Web-App auf dem Handy: Der Kartenpunkt neben einer MultiPass-Station ist jetzt ein Knopf mit 44 × 44 px statt eines 16 px breiten Symbols und lässt sich leicht antippen – in beiden Designs, auch in der Home-Assistant-App.
- Die Handy-App ist unverändert.

## 0.23.2 – 2026-11-21

- Mehr Tests für die Verbindung zu Tesla: ein abgelaufenes Zugriffstoken, der Zeitfilter, das Blättern durch viele Ladungen und das monatliche Abfrage-Budget. Im Gebrauch ändert sich nichts.
- Die Handy-App ist unverändert.

## 0.23.1 – 2026-11-21

- **Weniger Tesla-Abfragen, wenn Tesla um Geduld bittet.** Antwortet die Fleet API mit *Too many requests* (HTTP 429), wartet Ladecockpit jetzt so lange, wie Tesla sagt (`Retry-After`, sonst 5 Minuten), bevor es wieder fragt – auch bei den schnellen Abgleichen nach dem Laden –, statt die Anfrage zu wiederholen und das monatliche Abfrage-Budget aufzubrauchen. Im Log steht eine Zeile statt eines Fehlers mit Traceback; nach drei fehlgeschlagenen Abgleichen in Folge erscheint wie bisher die Problem-Benachrichtigung.
- Die Handy-App ist unverändert.

## 0.23.0 – 2026-11-21

- **Neuer Preis an einem Standort.** Hat sich der Preis eines Standorts geändert, sagt Ladecockpit das: „Neuer Preis in Willich: seit 20.11. kostet eine kWh 0,40 € statt 0,37 € (+0,03 €/kWh).“ Die Standort-Tabelle zeigt den aktuellen Preis jetzt neben dem Durchschnitt, der die älteren Ladungen weiter enthält. Eine Änderung zählt nur, wenn die Ladungen davor und danach jeweils einen einheitlichen Preis haben, die Preise mindestens 0,02 auseinanderliegen und einige Ladungen zur gleichen Tageszeit stattfanden – ein Preis nach Tageszeit oder ein Standort mit günstigem Nachtpreis gilt also nie als Änderung. Der Tipp bleibt 60 Tage stehen. Neues Feld `price_changes` in `/api/dashboard`, `price_now` und `price_since` in `sites`.
- **Langzeitstatistik in Home Assistant.** `sensor.ladecockpit_month_cost` hat jetzt `state_class: total` mit dem Monatsanfang als `last_reset`. Home Assistant behält die Monatssummen damit dauerhaft statt etwa zehn Tage. Neuer Sensor `sensor.ladecockpit_month_energy`: die in diesem Monat geladenen kWh (Rechnungen plus Laden zu Hause), ebenfalls mit Langzeitstatistik – er kann ins Energie-Dashboard.
- **Home-Assistant-Integration (optional).** `custom_components/ladecockpit`, über HACS als benutzerdefiniertes Repository installierbar, macht aus den Entitäten von Ladecockpit echte: mit eindeutiger ID und Gerät, umbenennbar, einem Bereich zuordenbar und gleich nach einem Neustart wiederhergestellt. Die Entitäts-IDs bleiben gleich; die Integration übernimmt die Zustände, die die App vorher geschrieben hat. Einzustellen gibt es nichts: Innerhalb von fünf Minuten findet die App die geladene Integration (`/api/config`) und schickt jeden Wert als Event `ladecockpit_state`, statt Zustände zu schreiben, einmal pro Stunde alle erneut. Ohne die Integration ändert sich nichts.
- Tests der Integration gegen Home Assistant selbst (`tests_ha`, eigener CI-Job); `httpx2` für den Testclient, damit die Tests nicht mehr warnen.
- Handy-App: eigenes Symbol für den Tipp zum neuen Preis.

## 0.22.0 – 2026-11-21

- **Referenzpreis aus deinen Rechnungen.** Ohne eigenen Referenzpreis nimmt Ladecockpit jetzt den Tagespreis deiner Standorte aus den Rechnungen: Ladungen nachts oder früh am Morgen an einem Standort mit günstigerem Nachtpreis zählen zum Tagespreis dieses Standorts, alle anderen zu ihrem eigenen Preis. Die Monatskarte zeigt „Zum Tagespreis deiner Standorte“, die Rechnungen und was das Laden zur günstigen Zeit gespart hat, und ein Tipp sagt es dazu („Laden nachts und früh am Morgen hat dir diesen Monat 9,00 € gespart …“). Verglichen werden nur ausgewiesene Preise, eine Preisänderung, ein teurer Standort oder eine Gutschrift von Tesla zählt also nie als Ersparnis; der Vergleich erscheint ab einer Ersparnis von 0,50. Eine *Entität Referenzpreis* oder ein *Referenzpreis pro kWh* hat weiter das letzte Wort, und `0` schaltet den Vergleich ab. Neue Felder `reference_source`, `reference_saving` und `reference_off_kwh` in `compare` von `/api/dashboard`.
- Die Demo zeigt den neuen Vergleich statt eines festen Referenzpreises.
- Die Handy-App ist unverändert; sie zeigt den neuen Tipp zusammen mit den anderen.

## 0.21.1 – 2026-11-21

- Abhängigkeiten aktualisiert: FastAPI 0.165.0, pypdf 7.1.1.
- Blueprint *Rechnung buchen*: Der Text der Ladung wird auf die Höchstlänge der Entität *Text der letzten Ladung* gekürzt (standardmäßig 100 Zeichen). Ein langer MultiPass-Betreibername lässt Home Assistant den Text also nicht mehr ablehnen und die weiteren Aktionen überspringen.
- Mehr Tests für die Verbindung zu Home Assistant (Zustände, Verlauf, Events, Fehler).
- Die Handy-App ist unverändert.

## 0.21.0 – 2026-11-21

- **Benachrichtigungen aufs Handy ohne Home Assistant.** Neue Optionen *Push aufs Handy (ntfy-Thema)* (`NTFY_URL`) und *ntfy-Zugangstoken* (`NTFY_TOKEN`): Ladecockpit schickt jede neue Rechnung („⚡ Neue Rechnung · Moers“ – kWh, Betrag, Preis pro kWh), Probleme mit der Tesla-Anmeldung oder dem Abgleich (und wenn sie gelöst sind) und den Monatsbericht an ein ntfy-Thema – auf ntfy.sh oder deinem eigenen Server. Abonnierst du dasselbe Thema in der ntfy-App (Android, iOS), kommen die Nachrichten auch an, wenn das Handy nicht im Heimnetz ist, und ohne den Home-Assistant-Blueprint. Gesendet werden nur Ladungen, die nach dem Setzen der Option beginnen, jede einmal. *Testnachricht senden* unter *Betrieb* in der Web-App prüft die Einrichtung (`POST /api/push/test`). Der Monatsbericht läuft jetzt auch bei Installationen ohne Home Assistant. Auf ntfy.sh ist der Name des Themas das Geheimnis: lang und zufällig wählen.
- Der Vergleich mit einem Verbrenner nimmt, was die Strecke wirklich gekostet hat: Die Zeile *Tesla* passt jetzt centgenau zu den Rechnungen (vorher wurde sie aus den gerundeten Kosten pro 100 km zurückgerechnet und konnte ein paar Cent abweichen), die Ersparnis damit auch. Neues Feld `distance_cost` in `month` und `monthly`.
- Die Handy-App ist unverändert.

## 0.20.0 – 2026-11-21

- **Einrichtung Schritt für Schritt.** Bis Ladecockpit läuft, zeigt die Web-App die Einrichtung als geprüfte Liste statt als feste Anleitung: Tesla-Entwickler-App → bei Tesla anmelden → erster Abgleich, danach (optional) Home Assistant, seine Entitäten und weitere Optionen. Jeder Schritt sagt, was Ladecockpit gerade sieht („Client ID ist gesetzt.“, „12 Ladungen abgerufen, letzte 21.11. 09:14“, „1 von 5 Entitäten liefert keinen passenden Wert“, eine abgelaufene Tesla-Anmeldung mit der Meldung von Tesla); der nächste offene Schritt ist markiert und öffnet seine Anleitung – die Tesla-Anleitung, die Anmeldung oder *Jetzt abgleichen*. *Erneut prüfen* liest alles neu ein. Sind alle nötigen Schritte erledigt, wandert die Liste in die eingeklappte *Einrichtungsprüfung*. `setup.checks.steps` in `/api/dashboard`, auch ohne Home Assistant.
- Die Einrichtungsprüfung warnt nicht mehr, dass *Zeit bis voll* oder *Ladeleistung* nicht verfügbar sind, solange das Auto nicht lädt – diese Entitäten haben nur beim Laden einen Wert („nur beim Laden“).
- Handy-App: Die Einrichtungskarte nennt den nächsten Schritt („Nächster Schritt: Bei Tesla anmelden“) und listet die Schritte, die offen sind oder ein Problem haben.

## 0.19.0 – 2026-11-21

- **Tipps als Karten.** Was Ladecockpit auffällt – die günstigste Zeit und der günstigste Standort, Nachtpreise, MultiPass, Blockiergebühren, langsame Ladungen, Gutschriften – steht jetzt als Karten weit oben in der Web-App und unter *Auswertung* in der Handy-App, jede mit einem Weg dorthin, worum es geht: „Radar für Mainz“, „Zu den Ladungen“ (die Handy-App füllt die Suche mit dem Standort), „Zu diesem Monat“.
- **Preis-Radar je Standort.** Chips über dem Radar wechseln von allen Standorten zu einem deiner häufigen Standorte (ab 3 Ladungen dort). Die Zeitfenster vermischen so nicht mehr die Preise verschiedener Standorte. `site_radar` in `/api/dashboard`.
- **Einrichtungsprüfung.** Web-App und Handy-App sagen, welche Optionen noch etwas bringen würden („Du hast einen Spritpreis-Sensor – mit *Spritpreis als Tagesdurchschnitt* …“, „Ohne *Entität Kilometerstand* gibt es keine Strecke …“), und zeigen jede Entität aus Home Assistant mit aktuellem Wert und Einheit – eine Entität, die fehlt, nicht verfügbar ist, keine Zahl liefert oder eine unerwartete Einheit hat, wird markiert. In der Home-Assistant-App sagt ein Hinweis, wie man Optionen einblendet, die die Konfiguration versteckt. `setup.checks` in `/api/dashboard`.
- **Kosten pro 100 km neben dem Verbrenner.** Das Monatsdiagramm der Web-App wechselt zwischen Kosten, kWh und Kosten pro 100 km, letztere für jeden Monat mit dem Verbrenner neben dem Tesla (`fuel_per_100` in `monthly`). Die Handy-App hat denselben Vergleich als eigenes Diagramm.
- **Handy-App: Vergleich mit einem Verbrenner.** Das Cockpit zeigt den Monat wie die Web-App: Verbrenner (mit dem Literpreis – Tagesdurchschnitt, bezahlt oder fest), Tesla und was du gespart hast.
- **Exporte an einem Ort.** Die Web-App sammelt CSV, Datensicherung (herunterladen und einspielen), Jahresübersichten und Monatsberichte mit ihren Rechnungen in einem Bereich *Exporte und Datensicherung*. Die Handy-App kann die Datensicherung jetzt auch teilen oder speichern.
- **Handy-App: Barrierefreiheit.** Zahlen, die Zeilen des Radars, der Vergleich und die Diagramme werden jeweils als ein Satz vorgelesen, Überschriften sind als Überschriften ausgezeichnet, und bei großer Systemschrift stehen die Zahlen des Monats einzeln untereinander.

## 0.18.0 – 2026-11-21

- **Spritpreis als Tagesdurchschnitt.** Neue Option *Spritpreis als Tagesdurchschnitt* (`FUEL_PRICE_DAILY`, standardmäßig aus): Der Vergleich mit einem Verbrenner berechnet die Strecke jedes Tages mit dem Tagesdurchschnitt von *Spritpreis aus Entität* – z. B. dem günstigsten E10-Preis in deiner Nähe, der sich viele Male am Tag ändert – statt mit dem Literpreis, den du bezahlt hast. Jeder Preis zählt so lange, wie er angezeigt wurde. Die Web-App zeigt den Durchschnitt über den Monat, gewichtet nach den Kilometern jedes Tages („Verbrenner (8,3 L/100 km · Ø 1,92 €/L je Tag)“); Monatsverlauf, Monatsbericht und Hochrechnung folgen. Ein Tag ohne Preis nimmt den nächstgelegenen Tag mit Preis (bis zu 7 Tage entfernt). Ladecockpit speichert die Werte der Spritpreis-Entität jetzt selbst und holt beim ersten Start die letzten 10 Tage aus Home Assistant; Monate davor behalten den bezahlten Preis.
- Die Handy-App ist unverändert.

## 0.17.0 – 2026-11-15

- **Nacht- und Tagpreis je Standort.** Viele Supercharger sind nachts und früh am Morgen günstiger als tagsüber. Ladecockpit findet jetzt beide Preise in deinen eigenen Rechnungen und zeigt sie unter dem Preis-Radar, in der Web-App und in der Handy-App: „Moers · Nacht 0,28 € · Tag 0,46 €“, mit den Zeiten, zu denen du günstig geladen hast, und wie viel weniger deine teuren kWh an diesen Standorten gekostet hätten. Zwei Preise bekommt ein Standort nur, wenn sie mindestens 0,06 €/kWh auseinanderliegen, jede günstigere Ladung vor 10 oder ab 20 Uhr begann und eine teurere tagsüber – sonst könnte eine Preisänderung als Tarif durchgehen. Bis du an einem Standort zu beiden Zeiten geladen hast, sagt der Abschnitt, wie er sich füllt. Neuer Tipp in den Auswertungen; `tariffs` in `/api/dashboard`.

## 0.16.1 – 2026-11-15

- Das Log sagt, was die Suche bei OpenStreetMap für jede Station gefunden hat und warum sie eine ohne Betreiber gelassen hat: „OpenStreetMap, Station in Hafenstadt: mehrere Betreiber in der Nähe (Fastned 30 m, Allego 45 m)“, „die Adresse wurde auf der Karte nicht gefunden“, „keine Ladestation im Umkreis von 400 m auf der Karte“. Genannt wird nur der Ort. Stationen, die bisher keinen Betreiber bekommen haben, werden noch einmal gefragt, damit der Grund nach dem Update erscheint.
- Die Handy-App ist unverändert.

## 0.16.0 – 2026-11-15

- **Betreiber in ganz Europa.** Bisher wusste Ladecockpit nur in Deutschland, wer eine MultiPass-Station betreibt (aus dem Register der Bundesnetzagentur); im Ausland zeigte es den Standortnamen oder eine Adresse. Jetzt fragt es für jede Station, die das Register nicht kennt, OpenStreetMap: Die Adresse aus der Rechnung wird zu einer Koordinate, und die Ladestationen drumherum verraten den Betreiber. Übernommen wird er nur, wenn die Karte keinen Zweifel lässt – alle Stationen im Umkreis von 400 m gehören einem Betreiber, oder eine liegt höchstens 50 m entfernt und der nächste andere Betreiber mindestens 50 m weiter; sonst bleibt die Station, wie sie war, statt einen falschen Namen zu bekommen. Jede Adresse wird einmal gefragt, höchstens 8 pro Abgleich; gesendet wird nur die Adresse der Station (an nominatim.openstreetmap.org und overpass-api.de). Neue Option *Betreiber über OpenStreetMap suchen* (`MAP_LOOKUP`, standardmäßig an). Kartendaten © OpenStreetMap-Mitwirkende.
- Firmennamen aus dem Register und der Karte erscheinen als die Marke, die man kennt: „Enel X Way Italia S.r.l.“ → „Enel X Way“, „The New Motion B.V.“ → „Shell Recharge“, „Aral AG“ → „Aral pulse“. Die Tabelle (`app/operators.py`) beginnt mit etwa 50 Namen europäischer Netze und wächst weiter.
- Was du selbst zuordnest, in der App oder unter *Betreiber selbst zuordnen*, hat weiter das letzte Wort.

## 0.15.0 – 2026-11-15

- **Den Betreiber einer Station in der App zuordnen.** Für Fremdstationen (MultiPass), deren Betreiber Ladecockpit nicht kennt: *Betreiber zuordnen* unter *Standorte* in der Web-App oder in den Details einer Ladung in der Handy-App. Aus den bekannten Betreibern wählen oder einen Namen eintippen. Das gilt sofort für jede Ladung an dieser Station – vergangene und künftige – ohne Neustart und ist Teil der Datensicherung. Die Option `SITE_OPERATORS` bleibt für ganze Gruppen von Stationen. API: `GET /api/operators`, `PUT /api/operator`.
- **Handy-App: Filter als Chips.** *Zeitraum*, *Netzwerk* und *Standort* stehen als Chips unter dem Suchfeld statt in einer eingeklappten Karte; ein aktiver Filter zeigt seinen Wert und verschwindet mit einem Tipp auf sein ✕. Eine Zeile darunter fasst zusammen, was zu sehen ist: „12 Ladevorgänge · 384,0 kWh · 142,10 €“.
- **Handy-App: Preis pro kWh bei jeder Ladung.** Mit einem Punkt, der eine günstige Ladung (grün) von einer teuren (orange) unterscheidet, gemessen an deinem eigenen Durchschnitt.
- Handy-App: Rechnungen lassen sich als PDF teilen oder speichern, und ein Doppeltipp vergrößert die angetippte Stelle und wieder zurück.
- Handy-App: Ein leeres Ergebnis sagt, warum („Keine Ladevorgänge für „…“ gefunden“), und bietet an, die Filter zurückzusetzen.
- MultiPass wird erklärt, wo es auftaucht: „bei einem anderen Betreiber geladen, über Tesla abgerechnet“. Die Zeile der Gutschrift heißt *Gutschrift von Tesla*.

## 0.14.6 – 2026-11-15

- **Open-Source-Apps von Tesla (experimentell).** Mit einer Client ID und ohne Client Secret meldet sich Ladecockpit per PKCE an, so wie Tesla es für „Open Source Apps“ vorsieht. Tesla beschränkt solche Apps auf seine Discovery-Stufe; ob Ladehistorie und Rechnungen dort verfügbar sind, muss sich im Gebrauch zeigen. Installationen mit Client Secret funktionieren wie bisher.
- Pakete aktualisiert: FastAPI 0.163.0, pypdf 7.1.0.

## 0.14.5 – 2026-11-14

- Handy-App: Rechnungen, Monatsberichte und die Jahresübersicht lassen sich mit zwei Fingern vergrößern. Vorher waren die Seiten nur in Bildschirmbreite lesbar.
- **Betreiber selbst zuordnen.** Außerhalb Deutschlands kann Ladecockpit oft nicht sagen, wer eine MultiPass-Station betreibt. Neue Option *Betreiber selbst zuordnen* (`SITE_OPERATORS`): ein Text aus Standortname oder Adresse, ein Gleichheitszeichen und der Betreiber, mehrere durch Semikolon getrennt – `Hafenstadt=Fastned; Parkhaus Mitte=Stadtwerke`. Was du dort setzt, hat das letzte Wort, und die Station zählt als MultiPass.

## 0.14.4 – 2026-11-14

- **Preis-Radar: Der niedrigste Preis ist wieder der günstigste.** 0.14.2 übersprang Zeitfenster und Standorte mit nur ein oder zwei Ladungen, sodass direkt neben einem niedrigeren Preis ein teurerer als „am günstigsten“ beschriftet sein konnte. Jetzt bekommt immer der niedrigste Preis die Beschriftung, und wenn wenig dahintersteht, sagt die App das: „am günstigsten · nur 1 Ladung“. Gilt für die Handy-App, die Web-App und den Tipp unter dem Radar.

## 0.14.3 – 2026-11-14

- Gleicher Inhalt wie 0.14.2, erneut veröffentlicht: Das Docker-Image und die APK von 0.14.2 waren nicht aus dem richtigen Stand gebaut. Wer die APK 0.14.2 installiert hat, installiert 0.14.3.

## 0.14.2 – 2026-11-14

- **Preis-Radar: Eine einzelne Ladung macht keine Tageszeit und keinen Standort mehr zum günstigsten.** Ein Zeitfenster braucht drei Ladungen und ein Standort zwei, bevor es als günstigstes genannt wird; bis dahin heißt es „zu wenige für eine Aussage“. Gilt für die Handy-App, die Web-App und den Tipp unter dem Radar.
- Handy-App: Die Übersichtskarte des Preis-Radars sagt jetzt, wozu jeder Preis gehört – günstigste Tageszeit und günstigster Standort, jeweils mit eigenem Preis –, statt beides unter einer Überschrift zu vermischen.
- Handy-App: Preise im Preis-Radar haben wie überall zwei Nachkommastellen, „1 Ladevorgang“ steht nicht mehr in der Mehrzahl, und die Zeilen unter den Zeitfenstern haben ihr überflüssiges „€/kWh“ verloren.
- `solid` in `slots` von `/api/dashboard` sagt, ob ein Zeitfenster genug Ladungen hat.

## 0.14.1 – 2026-11-12

- Handy-App: gebaut mit Flutter 3.50 und dem eigenständigen Paket `material_ui`, das die Material-Bibliothek ersetzt, die Flutter 3.50 abkündigt. Im Gebrauch ändert sich nichts.
- Web-App, Home-Assistant-App und Docker-Image sind unverändert.

## 0.14.0 – 2026-11-12

- **Handy-App: Ladungen durchsuchen.** Ein Suchfeld über der Liste findet Ladungen nach Ort, Betreiber oder Adresse, zusätzlich zu den drei Filtern. Die Liste umfasst jetzt bis zu 400 Ladungen statt 40.
- **Handy-App: optionale Sperre.** *App sperren* in den Verbindungseinstellungen fragt beim Öffnen und nach einer Minute im Hintergrund nach Fingerabdruck, Gesicht oder der PIN des Handys. Standardmäßig aus; ein Handy ohne Displaysperre sperrt die App nie.
- **Kürzere Ortsnamen.** Ladungen im eigenen Land stehen mit dem Ort in der Liste – *Moers* statt *Moers, Germany*. Ladungen im Ausland behalten das Land. `place` in `/api/dashboard` enthält den Namen.
- **Benachrichtigung bei jeder neuen Rechnung.** Ein zweiter Home-Assistant-Blueprint (`notify_invoice.yaml`) schickt Ort, kWh, Betrag und Preis an die Home-Assistant-App auf deinem Handy, auf Wunsch nur für Ladungen, die deutlich langsamer als üblich waren. Er braucht keine Helfer.

## 0.13.1 – 2026-11-12

- Handy-App: Im Filter der Ladevorgänge war die Beschriftung *Zeitraum* oben abgeschnitten; die Felder haben jetzt mehr Platz.
- Web-App, Home-Assistant-App und Docker-Image sind unverändert.

## 0.13.0 – 2026-11-12

- **Datensicherung und Wiederherstellung.** In der Web-App unter *Verbindungen & API-Kosten*: Ladehistorie, Messwerte und Rechnungen als eine Datei herunterladen und wieder einspielen, zum Beispiel auf einem anderen Gerät. Die Tesla-Anmeldung bleibt bewusst außen vor. Eine Datei wird geprüft, bevor sich etwas ändert; Ladungen, die schon an Home Assistant gemeldet wurden, werden nicht doppelt gebucht. Auch als `GET /api/backup.zip` und `POST /api/restore`.
- **Jahresübersicht.** Eine PDF-Seite je Jahr mit einer Zeile pro Monat – Ladungen, kWh, netto, MwSt., brutto und Gutschriften – dazu die Summe, der MultiPass-Anteil und das Laden zu Hause. Unter *Export* in der Web-App, in den Berichten der Handy-App und als `/api/year/2026.pdf`. `years` in `/api/dashboard` listet die Jahre mit Ladungen.
- **Geführte Einrichtung.** Ohne Tesla-Zugang führt die Web-App in fünf Schritten durch die Tesla-Entwickler-App, mit der Weiterleitungsadresse zum Kopieren. Die Demo bietet dieselbe Anleitung.
- **Handy-App auf Englisch.** Die App folgt der Sprache des Servers (`APP_LANG`) und vor der ersten Verbindung der Sprache des Handys. Zahlen und Datum folgen ebenfalls.
- **Handy-App ohne Verbindung.** Ist der Server nicht erreichbar, zeigt die App die letzten Zahlen, die das Handy gespeichert hat, mit Datum und Uhrzeit.

## 0.12.10 – 2026-11-12

- **Handy-App: deutsches Zahlenformat.** Beträge und Zahlen haben ein Dezimalkomma und einen Punkt zwischen den Tausendern: `65,10 €`, `0,40 €/kWh`, `1.234,5 kWh`.
- **Handy-App: klarere Karten im Cockpit.** *Letzter Ladevorgang* zeigt unter dem Titel Standort, Datum und Betrag statt einer internen ID, *Gesamt* Ladungen, Energie und Kosten, *Ladeprognose* die Prognose und *Fahrzeug* Modell, Lack und Felgen. Aufgeklappt listen die Karten nur, was etwas bedeutet: keine internen IDs oder Bildadressen, Gebühren und Gutschriften nur, wenn es welche gibt. Als Netz steht Supercharger oder MultiPass da.
- Handy-App: Der Prognosetext wurde durch einen Strich ersetzt, wenn er ein großes T enthielt; behoben.
- Handy-App: Die Hinweise unter Serveradresse und Passwort werden nicht mehr abgeschnitten.
- Web-App, Home-Assistant-App und Docker-Image sind unverändert.

## 0.12.9 – 2026-11-12

- **Handy-App: keine grauen Kästen mehr.** Die aufklappbaren Karten (Verbindungen, letzte Ladung, Summen, Ladeprognose, Fahrzeug, Filter, Standorte, Monate) erschienen als graue Kästen und luden nichts. Sie lasen ihren Auf-/Zu-Zustand aus demselben Speicherplatz wie die Scrollposition der Seite und scheiterten daran. Jede Karte hat jetzt ihren eigenen Platz.
- Handy-App: Die Zahlen in der Monatsübersicht werden kleiner, statt abgeschnitten zu werden, wenn ein Titel zwei Zeilen braucht.
- Neue Tests zeichnen jeden Tab und jede Karte der Handy-App mit Demo-Daten und mit jeweils einem fehlenden Teil der Daten.
- Web-App, Home-Assistant-App und Docker-Image sind unverändert.

## 0.12.8 – 2026-11-12

- **Die Handy-App meldet Updates.** Unter Android fragt die App einmal pro Start bei GitHub, ob es ein neueres Release gibt, und zeigt ein Banner mit *Update laden*; Android bietet dann an, die APK über die installierte App zu installieren. Abgerufen werden nur die öffentlichen Release-Angaben, Ladedaten werden nicht gesendet. Die Prüfung lässt sich in den Verbindungseinstellungen abschalten (*Nach Updates suchen*). Test-Builds und iOS prüfen nie.
- Web-App, Home-Assistant-App und Docker-Image sind unverändert.

## 0.12.7 – 2026-11-12

- **Android-App zum Herunterladen.** Jedes Release hat jetzt eine signierte APK im Anhang (`ladecockpit-<version>.apk` mit ihrer SHA-256-Prüfsumme). Sie installiert sich als Update über die vorige, ein GitHub-Konto ist nicht nötig.
- Handy-App: Die App-ID ist jetzt `io.github.uekala.ladecockpit` für Android und iOS. Ein Test-Build mit der alten ID `com.example.ladecockpit` muss einmal deinstalliert werden.
- Handy-App: Die Monatsübersicht zeigt Kosten und Durchschnittspreis mit zwei Nachkommastellen.
- `mobile/tool/setup-android-signing.sh` brach mit einem Syntaxfehler ab; behoben und mit Tests abgedeckt.
- Neue Bildschirmfotos im README.
- Web-App, Home-Assistant-App und Docker-Image sind unverändert.

## 0.12.6 – 2026-11-11

- **Handy-App im neuen Design.** Dunkles Cockpit-Design mit Auto und Akku im Mittelpunkt, größeren Zahlen und klareren Karten. Die Funktionen sind unverändert.
- Android-Signierung: Ein Skript richtet den Signierschlüssel auf dem eigenen Rechner ein (`mobile/tool/setup-android-signing.sh`); `mobile/README.md` beschreibt, wie man ein signiertes Update prüft.
- Web-App, Home-Assistant-App und Docker-Image sind unverändert.

## 0.12.5 – 2026-11-11

- **Die Handy-App verbindet sich mit jedem Ladecockpit im eigenen Netz.** Unverschlüsseltes HTTP wird für Tailscale-Adressen (`100.64.0.0/10`, `*.ts.net`), Heimnetze (`10.x`, `172.16–31.x`, `192.168.x`, `fc00::/7`) und lokale Namen (`*.local`, `*.home.arpa`, `*.internal`, Namen ohne Punkt) akzeptiert. Jede andere Adresse braucht HTTPS. Vorher war unverschlüsseltes HTTP nur für eine feste Adresse erlaubt.
- **Docker ohne Home Assistant, beschrieben.** Das README führt durch die eigenständige Einrichtung; Home Assistant bleibt durchgehend optional. Hinweis für Docker-Nutzer: Seit 0.12.3 braucht eine Live-Installation `APP_PASSWORD` (HTTP Basic Auth), um zu starten. Der Demo-Modus nicht.
- Handy-App: Ein unbekannter Verbindungsfehler zeigt seine Diagnose in einer eigenen Zeile.
- Android-Builds werden mit einem dauerhaften Schlüssel signiert, sobald er im Repository eingerichtet ist, sodass sich eine neue APK als Update installiert.
- Fehlermeldungen und Ideen haben eigene Issue-Formulare.
- Abhängigkeiten aktualisiert: fastapi 0.161.1 → 0.162.4, fpdf2 2.8.9 → 2.9.0, pypdf 6.21.4 → 7.0.1, pypdfium2 5.14.0 → 5.15.2, tzdata ≥ 2026.6. GitHub Actions auf Versionen umgestellt, die unter Node 24 laufen.

## 0.12.4 – 2026-11-09

- **Monatsbericht und Rechnungsansicht bleiben nicht mehr an einer kaputten Rechnungsdatei hängen.** Ein Download, der kein PDF ist oder abgebrochen wurde, wird nicht mehr behalten; Ladecockpit holt die Rechnung beim nächsten Bedarf erneut.
- Abhängigkeiten aktualisiert: pypdf 6.21.2 → 6.21.4 (Sicherheitskorrekturen).

## 0.12.3 – 2026-11-08

- **Sicherer Zugang für die Handy-App.** Die optionale Einstellung *Mobiles App-Passwort* schützt den direkten Zugriff auf Port 8077 mit HTTP Basic Auth. Der direkte Zugriff bleibt gesperrt, bis ein Passwort gesetzt ist; Ingress nutzt weiter die Anmeldung von Home Assistant.
- Der direkte Port ist optional und darf nur in einem vertrauenswürdigen privaten Netz oder VPN genutzt werden. Nie öffentlich freigeben.

## 0.12.2 – 2026-11-07

- **Ladestationen nach ihrer Rechnungsadresse getrennt.** Verwendet Tesla für verschiedene Stationen denselben allgemeinen Standortnamen, hält Ladecockpit diese Orte in der MultiPass-Übersicht und der Standort-Statistik jetzt auseinander, wenn sich ihre Adressen aus den Rechnungen unterscheiden. Das behebt Fälle wie zwei ALDI-Stationen in Krefeld, die als ein Ort erschienen.

## 0.12.1 – 2026-11-02

- **Genauere Treffer im Ladesäulenregister.** Rechnung und Register schreiben eine Straße nicht immer gleich („Brunnenhaustraße“ und „Brunnenhausstr.“). Fast gleich geschriebene Straßen zählen jetzt als dieselbe Straße, und dieselbe Hausnummer geht vor einer nahen – vorher konnte eine Station den Betreiber eines Nachbarstandorts weiter die Straße hinunter bekommen. Stationen, die nach der alten Regel zugeordnet wurden, werden einmal neu nachgeschlagen.
- **Das im Standortnamen genannte Ladenetz hat Vorrang.** „Aral pulse Brassertstraße 124“ zeigt *Aral pulse*, nicht die Firma dahinter im Register (BP Europa). Nennt der Standortname nur einen Gastgeber – einen Supermarkt wie Aldi, Lidl oder Kaufland oder „Stadtwerke“ –, sagt weiter das Register, wer die Station betreibt.

## 0.12.0 – 2026-11-02

- **Betreiber statt Adressen.** MultiPass-Stationen erscheinen jetzt mit der Firma, die sie betreibt, und der Adresse darunter – „SEW · Brunnenhausstraße 46, Neustadt“ statt „Brunnenhausstr. 46, Neustadt“, „Electra“ statt „Neustadt - KiK“. Ladecockpit holt die Rechnung jeder MultiPass-Ladung einmal, liest die Adresse der Station und schlägt Stationen in Deutschland im öffentlichen Ladesäulenregister der Bundesnetzagentur nach (gleiche Postleitzahl und Straße, gleiche oder nächste Hausnummer). Das Register wird nur heruntergeladen, wenn eine neue Station dazukommt, höchstens alle 12 Stunden, Zeile für Zeile gelesen und nicht aufbewahrt. Außerhalb Deutschlands oder ohne Treffer im Register kommt der Betreiber weiter aus dem Standortnamen. Neue Option *Betreiber im Ladesäulenregister nachschlagen* (`OPERATOR_LOOKUP`, standardmäßig an).
- Betreiber und Adresse stehen in der Liste der Ladungen, der Standort-Tabelle, der MultiPass-Karte (ihr Kartenlink sucht jetzt die Adresse), der Karte der letzten Ladung, `sensor.ladecockpit_multipass` und `sensor.ladecockpit_last_charge` (`operator`, `address`), dem Event an Home Assistant (`operator`, `address` und der Betreiber in `text`), dem CSV-Export (zwei neue Spalten am Ende) und dem Monats-PDF. Der Preistipp nennt sie auch („SEW (Brunnenhausstraße 46, Neustadt)“).
- Der Kurzname aus dem Register wird genommen, wenn er den Betreiber nennt („SEW“ statt „SEW Seestadt Energie und Wasser“); lange Firmennamen werden auf das gekürzt, wie man sie nennt.
- **Die Rechnungsnummer entscheidet über das Netz.** Tesla schreibt die Rechnungsnummer in den Dateinamen der Rechnung: Reihe „P“ für Supercharger, „MSP“ für MultiPass. Das legt das Netz jetzt vor jedem anderen Hinweis fest – ohne das PDF herunterzuladen –, sodass ein Supercharger auf einem Supermarktparkplatz ein Supercharger bleibt. Supercharger-Rechnungen werden nicht mehr nur zur Prüfung des Netzes heruntergeladen.
- **Die Tesla-Anmeldung bleibt nach einem Aussetzer bestehen.** Eine einzelne abgelehnte Token-Erneuerung markiert die Tesla-Anmeldung nicht mehr als abgelaufen (und schickt keine Problem-Benachrichtigung mehr); erst eine zweite in Folge.
- Das Ladesäulenregister wird im Hintergrund gelesen, die Web-App reagiert dabei weiter.

## 0.11.3 – 2026-11-02

- **Sauberes Beenden.** Wenn Home Assistant die App stoppt oder aktualisiert, endet Ladecockpit nach dem Herunterfahren jetzt mit Exitcode 0 statt 143. Home Assistant warnt nicht mehr, die App habe „SIGTERM nicht behandelt“. Hintergrundaufgaben räumen auf, bevor der Prozess endet.
- **Shell-Stationen erkannt.** „OBN 0317 - Shell Diessemer Bruch“ zeigt jetzt den Betreiber *Shell Recharge* statt der Stationsnummer „OBN 0317“: Shell gilt als bekanntes Netz, und eine Stationsnummer vor dem Bindestrich wird nie als Betreiber genommen.

## 0.11.2 – 2026-11-01

- **MultiPass nach Preis.** Bis die Rechnung geprüft ist, zählt eine Ladung als MultiPass, deren Standortname nicht die Form hat, die Tesla seinen Superchargern gibt („Ort, Land“, z. B. „Bergstadt, Germany“), und die mehr als 0,50 €/kWh gekostet hat – auch wenn der Betreiber keine bekannte Marke ist. Supercharger, die zu Spitzenzeiten teuer sind, bleiben Supercharger. Neue Einstellung `MULTIPASS_MIN_PRICE` (Option *MultiPass ab Preis* in der Home-Assistant-App), 0 schaltet die Regel ab.
- Der Betreiber einer MultiPass-Station wird jetzt auch aus dem Teil des Standortnamens vor dem Bindestrich genommen („Green Energy Nord - AC E5“ → „Green Energy Nord“), sodass `operators` in `sensor.ladecockpit_multipass` auch Netze listet, die nicht auf der Markenliste stehen. Ein Ort wird nicht für ein Netz gehalten: Ist der Teil vor dem Bindestrich ein Ort aus deinen eigenen Standortnamen („Neustadt - KiK“, mit Neustadt aus „Brunnenhausstr. 46, Neustadt“ oder einem Supercharger wie „Bergstadt, Germany“), bleibt der Betreiber leer.
- Beides stand schon unter 0.11.1, war aber nicht in dessen Image.

## 0.11.1 – 2026-11-01

- **MultiPass an der Rechnung erkannt.** MultiPass-Ladungen an Stationen, deren Name nichts verrät (z. B. „Brunnenhausstr. 46, Neustadt“ oder „Green Energy Nord - AC E5“), wurden als Supercharger-Ladungen gezählt. Ladecockpit liest das Netz jetzt aus der Rechnung: MultiPass-Rechnungen haben eine Nummer mit „MSP“ (Tesla als Mobilitätsanbieter), Supercharger-Rechnungen nicht. Die Rechnung jeder neuen Ladung wird einmal geholt, bevor die Ladung an Home Assistant geht, und aufbewahrt – sie oder den Monatsbericht anzusehen braucht dann keine weitere Abfrage. Nach dem Update werden die Ladungen der letzten 120 Tage geprüft, höchstens 25 pro Abgleich. Die Rechnung hat das letzte Wort, auch gegenüber dem Betreibernamen: Ein Supercharger auf einem Supermarktparkplatz bleibt ein Supercharger.
- Heruntergeladene MultiPass-Rechnungen heißen `multipass-….pdf`.
- Die Tests schlagen am Monatsersten nicht mehr fehl.

## 0.11.0 – 2026-10-27

- **Neues Design: Dynamisch.** Es ersetzt *Modern* (wer Modern genutzt hat, bekommt Dynamisch). Ein Cockpit bei Nacht, immer dunkel: Der Akku ist ein leuchtender Ring mit Strichen, Untergrenze und Ladelimit, neben dem Bild deines Autos. Beim Öffnen der Seite steigen die Kacheln nacheinander auf, der Ring zeichnet sich, Zahlen zählen hoch und Balken wachsen. Das Licht der Seite folgt dem Akku – grün, bernsteinfarben, wenn er knapp wird, rot unter der Untergrenze, cyan beim Laden – und der Tageszeit. Das Preis-Radar markiert das Zeitfenster, in dem du gerade bist; ein Tipp auf ein Fenster zeigt Ladungen, kWh und den Abstand zu deinem Durchschnitt. Ein Tipp oder Zeigen auf einen Monat im Verlauf zeigt seine Zahlen. Die Liste der Ladungen zeigt die neuesten sechs und öffnet den Rest auf Wunsch. Zahlen in Saira, Text in Geist (beide SIL Open Font License, mit der App ausgeliefert). *Klassisch* bleibt, wie es war, und bleibt der Standard.
- **Live beim Laden.** Während das Auto lädt, zeigt die Web-App *Lädt* mit der Leistung, wann das Ladelimit erreicht ist und wie lange das dauert, sekündlich heruntergezählt. Ladecockpit fragt Home Assistant beim Laden alle 15 Sekunden statt jede Minute, und die Web-App aktualisiert sich genauso oft. Zwei neue optionale Entitäten: *Entität Ladeleistung* (z. B. `sensor.my_tesla_charger_power`) und *Entität Zeit bis voll* (z. B. `sensor.my_tesla_time_to_full_charge`, ein Zeitstempel oder eine Dauer). Ohne sie wird das Ende aus der Leistung und den kWh pro Prozent geschätzt oder daraus, wie schnell der Akkustand steigt.
- Während das Auto lädt, wird der nächste Ladestopp vom Ladelimit aus berechnet.
- Die Demo zeigt jetzt ein Auto, das an einem Supercharger lädt.
- `status` in `/api/dashboard` hat `charging`, `power`, `rate` (% pro Stunde) und `finish`. `PUT /api/look` nimmt `classic` oder `dynamic` (`modern` funktioniert weiter und bedeutet `dynamic`).

## 0.10.0 – 2026-10-27

- **Der Spritpreis, den du wirklich bezahlt hast.** Der Verbrenner-Vergleich kann statt eines festen Preises oder des aktuellen Preises einer Tankstelle nehmen, was du wirklich pro Liter bezahlt hast. Dafür gibt es zwei neue Optionen, *Tankkosten gesamt* und *Getankte Liter gesamt* – zwei Entitäten, die mit jedem Tanken wachsen, z. B. die Helfer eines Tankbuchs in Home Assistant. Ladecockpit speichert täglich beide Werte und nimmt den Durchschnitt der letzten 90 Tage; bis 90 Tage beisammen sind oder nachdem die Summen zurückgesetzt wurden, nimmt es alles, was die Summen enthalten. Der bezahlte Preis geht vor *Spritpreis aus Entität* und dem festen Spritpreis; die Monatskarte sagt „… €/L bezahlt“, und ein Tipp zeigt, auf wie vielen Litern der Durchschnitt beruht.
- `compare.fuel` in `/api/dashboard` hat `source` (`paid`, `entity` oder `fixed`), `paid_days` und `paid_litres`.

## 0.9.0 – 2026-10-27

- **Design wählen: klassisch oder modern.** Ganz unten in der Web-App wechselt *Design* zwischen zwei Designs. *Klassisch* ist das Design von 0.8, ruhig und nah an der App des Autos. *Modern* ist neu: Preise tragen die Farben des Energielabels, von Dunkelgrün (günstiger als dein Durchschnitt) bis Rot (teurer) – das Preis-Radar wird zu Pfeilen auf dieser Skala, Standorte und Ladungen zeigen ihre Preisfarbe, und eine kleine Skala erklärt sie. Alles andere ist Tinte auf Papier: Bricolage Grotesque mit schmalen fetten Zahlen, ein Akkubalken aus 20 Segmenten wie im Display eines Autos, umrandete Knöpfe, Kacheln mit Haarlinie. Dunkel- und Hellmodus folgen in beiden Designs dem Gerät.
- Die Wahl wird in Ladecockpit gespeichert, jedes Handy und jeder Rechner zeigt also dasselbe. Klassisch bleibt der Standard.
- Beide Designs bringen ihre Schriften mit (Geist; Bricolage Grotesque). Ein Browser lädt nur die Dateien des genutzten Designs.
- Neue API: `PUT /api/look` mit `{"look": "classic"}` oder `{"look": "modern"}`; `GET /api/dashboard` hat `look`.

## 0.8.0 – 2026-10-27

- **Neues Design, ruhiger und näher an der App des Autos.** Auto und Akku eröffnen die Seite ohne Rahmen: das Bild deines Autos, der Akkustand in großen hellen Zahlen und ein schmaler grüner Akkubalken mit markiertem Ladefenster. Darunter flache Kacheln ohne Rahmen und Schatten, Zeilen mit dünnen Trennlinien statt gepunkteter Führungslinien, schlichte Tabellenziffern statt einer Schreibmaschinenschrift, Beschriftungen in normaler Schreibweise. Schwarz im Dunkelmodus, Weiß im Hellmodus, Blau für Aktionen und Balken, Grün für den Akku und das günstigste Zeitfenster.
- Die Monatskarte nimmt die volle Breite ein: Summe und Zahlen links, die Vergleichszeilen rechts.
- Die Schrift (Geist, SIL Open Font License) kommt mit Ladecockpit, die Seite lädt also keine Schriften mehr von Google.
- Auf Handys braucht der Kopf eine Zeile weniger, und der Name des Autos und *Anpassen* stehen nebeneinander.

## 0.7.1 – 2026-10-26

- **Übersichtlichere Monatskarte.** Die Zeilen unter der Monatssumme sind gruppiert, das Nützlichste zuerst: woraus sich die Summe zusammensetzt (nur bei mehr als einem Teil), der Vergleich mit einem Verbrenner, der Abgleich mit deinem Referenzpreis und der Sprit eines anderen Autos – jede Gruppe durch eine Linie getrennt.
- Der Verbrenner-Vergleich sagt jetzt, welche Strecke er nimmt (z. B. „604 km seit 16.10.“, wenn die Kilometerstände mitten im Monat beginnen), und zeigt die Tesla-Kosten für genau diese Strecke, sodass *Verbrenner − Tesla = gespart* auf der Karte aufgeht. Vorher konnte die Verbrenner-Zahl kleiner wirken als die Monatssumme, obwohl Geld gespart wurde.

## 0.7.0 – 2026-10-25

- **Langsame Ladungen.** Die mittlere Leistung jeder Ladung wird mit dem verglichen, was dein Auto am selben Supercharger üblicherweise bekommt (der Median deiner anderen Ladungen dort mit mindestens 20 kWh). Eine Ladung mit weniger als 60 % davon wird in der Liste der Ladungen (mit dem üblichen Wert) und auf der Karte der letzten Ladung markiert, und ein Tipp nennt die jüngste mit den häufigen Gründen: ein kalter Akku ohne Vorkonditionierung oder eine geteilte oder gedrosselte Ladesäule. Kurze Ladungen und Ladungen, die über 50 % Akku begonnen haben, gelten nie als langsam, weil sie absichtlich langsamer laden.
- Das Event `ladecockpit_invoice`, der Blueprint und `sensor.ladecockpit_last_charge` enthalten `avg_power_kw`, `typical_power_kw` und `slow` (der Sensor auch `start_soc`), z. B. um eine langsame Ladung in der Benachrichtigung zu erwähnen.
- Die Demo hat eine langsame Ladung nach einer langen Fahrt.

## 0.6.2 – 2026-10-25

- **Rechnungen in der Home-Assistant-App.** In der Companion-App von Home Assistant auf dem Handy taten die PDF-Links nichts oder endeten in einem Anmeldefehler: Die App hat keinen PDF-Betrachter, und Links, die ein neues Fenster öffnen, lassen die Anmeldung von Home Assistant zurück. In der App öffnen *Rechnung (PDF)* und der Monatsbericht jetzt eine Ansicht innerhalb von Ladecockpit mit den Seiten als Bilder (Tipp auf eine Seite vergrößert, Zurück schließt), mit einem Knopf *Herunterladen*, der das PDF aufs Handy speichert. ZIP- und CSV-Export laden genauso herunter. In einem normalen Browser ändert sich nichts.
- Neue API: `GET /api/invoice/<id>/pages`, `GET /api/invoice/<id>/page/<n>.png` und dasselbe für `/api/report/<JJJJ-MM>`. Rechnungsseiten werden einmal gezeichnet und neben dem PDF zwischengespeichert.

## 0.6.1 – 2026-10-25

- **Ruhigeres Log.** Ladecockpit schreibt nicht mehr jede Anfrage an Home Assistant und Tesla (etwa ein Dutzend Zeilen pro Minute) und die Zustandsprüfung ins Log. Warnungen und Fehler erscheinen weiter, echte Probleme fallen also wieder leicht auf.

## 0.6.0 – 2026-10-24

- **Wo MultiPass funktioniert hat.** Eine neue Liste aller Fremdstationen, an denen eine MultiPass-Ladung auf deinen Rechnungen steht: Betreiber, Ladungen, Durchschnittspreis, letzte Nutzung und ein Link, der die Station in Google Maps sucht. Die Betreiber erscheinen als Chips, du siehst also, welche Netze MultiPass bei dir schon angenommen haben. Die Liste ordnet nur Rechnungen neu, die Ladecockpit schon hat – keine zusätzlichen Tesla-Abfragen.
- Neue Entität `sensor.ladecockpit_multipass`: die Zahl dieser Stationen als Zustand, die Liste als Attribut `stations` (mit `map_url`), dazu `operators` und ein fertiger `text`. Der fertige Dashboard-Abschnitt zeigt sie, sobald es eine Station gibt.
- Die Demo hat eine zweite MultiPass-Station.

## 0.5.0 – 2026-10-24

- **Bild deines Autos.** Die Web-App zeigt deinen Tesla, gezeichnet von Teslas eigenem Konfigurator. Modell und Generation (Model S, 3, X und Y seit 2012, Cybertruck), Ausstattung (z. B. Performance oder Plaid), Felgen, Lack und Ansicht wählst du unter **Anpassen**. Angeboten werden nur Kombinationen, die Tesla zeichnen kann. Ohne Auswahl werden Modell und Generation an der VIN erkannt.
- Neue Entität `sensor.ladecockpit_car`: der Name des Autos als Zustand, sein Bild als Entitätsbild, dazu `image`, `image_front`, `image_side` und `image_rear` für Dashboards. Der fertige Dashboard-Abschnitt zeigt es.
- Neue API: `GET /api/car`, `POST /api/car/preview`, `PUT /api/car`, `DELETE /api/car`.

## 0.4.1 – 2026-10-23

- Neue Entitäten `sensor.ladecockpit_range_at_100` (mit Langzeitstatistik, für einen Verlauf der Akkugesundheit über Monate) und `sensor.ladecockpit_consumption` (abgerechnete kWh pro 100 km/mi in diesem Monat, dazu der Verbrauch nach Außentemperatur als Attribut `by_temperature`).

## 0.4.0 – 2026-10-23

- **MultiPass**: Ladungen an Fremdsäulen, die über Tesla MultiPass bezahlt werden, werden in der Tesla-Ladehistorie erkannt und getrennt gezeigt (Liste der Ladungen, Standorte, Monat, Preisvergleich). Das Event `ladecockpit_invoice`, der Blueprint und `sensor.ladecockpit_last_charge` enthalten `network` (`supercharger` oder `multipass`); `sensor.ladecockpit_month_cost` hat `multipass_cost` und `multipass_sessions`. Der CSV-Export hat eine neue letzte Spalte.
- **Ersparnis gegenüber einem Verbrenner**: Mit einem Verbrauch und einem Spritpreis (fest oder aus Entitäten) zeigt der Monat, was die Strecke mit Benzin oder Diesel gekostet hätte und was du gespart hast. Neue Optionen `fuel_consumption`, `entity_fuel_consumption`, `fuel_price`, `entity_fuel_price`.
- **Hochrechnung**: Kosten und Strecke pro Jahr aus den letzten 90 Tagen, mit der Ersparnis gegenüber dem Verbrenner.
- **Ladeplan**: Die Karte zum nächsten Stopp sagt, wann und wo du laden solltest, bevor der Akku die Untergrenze erreicht – der günstigste Supercharger und das günstigste Zeitfenster aus deinen eigenen Rechnungen, mit der erwarteten Ersparnis (`plan` an `sensor.ladecockpit_next_charge`).
- **Monatsbericht**: Am Monatsersten das Event `ladecockpit_month_report` mit den Zahlen des Vormonats und einem fertigen Text, dazu eine Benachrichtigung in Home Assistant (Option `month_report`).
- **Tesla-Gutschriften**: Ladungen, die teilweise mit Tesla-Guthaben bezahlt wurden (z. B. kostenloses Supercharging bei einem Neuwagen), zeigen jetzt Listenpreis und Gutschrift. Preis-Radar, Standorte, Ladeplan und MultiPass-Vergleich nutzen den Listenpreis, eine Gutschrift lässt einen Supercharger also nicht mehr günstig aussehen. Bezahlte Beträge sind unverändert. Der CSV-Export hat Listenpreis, Gutschrift und Nettobetrag.
- **Laden zu Hause**: optionaler Wallbox-Zähler und Strompreis (fest oder als Entität, bewertet zum Zeitpunkt des Ladens). Fließt in Monat, Kosten pro 100 km/mi, Ersparnis und Hochrechnung ein (`entity_home_energy`, `home_price`, `entity_home_price`). `sensor.ladecockpit_month_cost` ist jetzt die Summe inklusive Laden zu Hause (`invoice_cost`, `home_cost` als Attribute).
- **Akkugesundheit**: Reichweite bei 100 % im Zeitverlauf und der Supercharger-Anteil an der geladenen Energie (`range_at_100` an `sensor.ladecockpit_battery`).
- **Verbrauch nach Außentemperatur** (`entity_outside_temp`, Sensor oder Wetter-Entität).
- **Monats-PDF** `/api/report/<JJJJ-MM>.pdf`: Deckblatt mit netto, MwSt., brutto und Gutschriften, danach alle Rechnungen des Monats.
- Das Log nennt Felder in Teslas Ladehistorie, die Ladecockpit noch nicht kennt.
- Preistipps erscheinen nur bei Unterschieden ab 0,03 €/kWh.
- Behoben: Die Web-App scrollt auf schmalen Handys nicht mehr seitwärts.

## 0.3.0 – 2026-10-23

- **Sensoren in Home Assistant**: Ladecockpit legt `sensor.ladecockpit_next_charge`, `sensor.ladecockpit_battery`, `sensor.ladecockpit_month_cost`, `sensor.ladecockpit_last_charge`, `sensor.ladecockpit_price_tip` und `binary_sensor.ladecockpit_problem` jetzt selbst an. Kein YAML nötig. Option `publish_entities` / `PUBLISH_ENTITIES`.
- Fertiger Dashboard-Abschnitt mit eingebauten Karten: `homeassistant/dashboard_card.yaml`.
- Die REST-Sensoren in `homeassistant/ladecockpit_package.yaml` sind entfallen. Wer sie kopiert hat, entfernt sie, sonst kollidieren sie mit den neuen Entitäten.

## 0.2.1 – 2026-10-23

- Behoben: Bei einer Neuinstallation wurden Akkustand, Reichweite und Kilometerstand nicht aus dem Verlauf von Home Assistant übernommen (abgefragt wurde nur der erste der zehn Tage). Sie erscheinen jetzt sofort, auch wenn das Auto schläft und seine Entitäten `unknown` sind.

## 0.2.0 – 2026-10-23

- **Läuft als Home-Assistant-App**: aus diesem Repository in Home Assistant installieren, die Web-App öffnet sich über die Seitenleiste. Kein eigener Server oder PC nötig.
- Ladeleistung (mittlere kW) je Ladung und je Standort.
- kWh pro 100 km/mi (abgerechnete Energie inklusive Ladeverlusten) je Monat.
- Export: alle Ladungen als CSV, alle Rechnungen eines Monats als ZIP-Datei.
- Benachrichtigung in Home Assistant, wenn die Tesla-Anmeldung abgelaufen ist oder der Abgleich wiederholt fehlschlägt (Event `ladecockpit_problem`).
- Bei einer Neuinstallation werden Akkustand, Reichweite und Kilometerstand aus dem Verlauf von Home Assistant übernommen und erscheinen sofort.
- Die Web-App lässt sich mit eigenem Symbol auf den Startbildschirm eines Handys legen.
- Der Container läuft jetzt als root (nötig für die Home-Assistant-App).

## 0.1.0 – 2026-10-23

Erste öffentliche Version.

- Holt Supercharger-Rechnungen über die Tesla Fleet API (nur lesend) und schickt jede einmal als Event `ladecockpit_invoice` an Home Assistant.
- Blueprint, um Rechnungen in eigene `input_number`- und `input_text`-Helfer zu buchen.
- Erkennt das Ende einer Ladung an einer Entität in Home Assistant und sucht sofort nach der Rechnung.
- Web-App (Englisch/Deutsch) mit letzter Rechnung, Monatskosten, Kosten pro 100 km/mi, Preis-Radar nach Tageszeit und Standort, Prognose für den nächsten Ladestopp, Abgleich mit den Summen in Home Assistant und Verbrauch der Tesla-API.
- Führt eine eigene Historie von Akkustand und Kilometerstand, damit der letzte Wert sichtbar bleibt, während das Auto offline ist.
- Demo-Modus ohne Zugangsdaten.
