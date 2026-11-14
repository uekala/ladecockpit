// English texts of the app, keyed by the German text in the code.
// A text that is missing here stays German.
const Map<String, String> english = {
  'Ladecockpit':
      'Ladecockpit',
  'Bitte zuerst die Serveradresse einrichten.':
      'Please set up the server address first.',
  'Bitte eine gültige HTTP- oder HTTPS-Serveradresse eingeben.':
      'Please enter a valid HTTP or HTTPS server address.',
  'Unverschlüsseltes HTTP ist aus Sicherheitsgründen nur im eigenen Netz erlaubt (Tailscale oder Heimnetz). Für andere Adressen bitte HTTPS verwenden.':
      'For security, plain HTTP is only allowed inside your own network (Tailscale or home network). Please use HTTPS for other addresses.',
  'die Rechnung':
      'the invoice',
  'Die Rechnung ist auf dem Server noch nicht verfügbar.':
      'The invoice is not available on the server yet.',
  'Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.':
      'Sign-in failed. Please check the app password.',
  'CSV-Export fehlgeschlagen (HTTP {0}).':
      'CSV export failed (HTTP {0}).',
  'Für diesen Monat sind keine Rechnungen vorhanden.':
      'There are no invoices for this month.',
  'Rechnungs-ZIP fehlgeschlagen (HTTP {0}).':
      'Invoice ZIP failed (HTTP {0}).',
  'den Monatsbericht':
      'the month report',
  'die Jahresübersicht':
      'the year overview',
  'Anmeldung fehlgeschlagen (HTTP 401/403). Bitte App-Passwort und Zugriffsrechte prüfen.':
      'Sign-in failed (HTTP 401/403). Please check the app password and access rights.',
  'Server antwortet mit HTTP {0}.':
      'The server answers with HTTP {0}.',
  'Ungültige Antwort vom Ladecockpit.':
      'Invalid answer from Ladecockpit.',
  'Zeitüberschreitung: Der Server hat nicht rechtzeitig geantwortet. Bitte Verbindung prüfen und erneut versuchen.':
      'Timeout: the server did not answer in time. Please check the connection and try again.',
  'Sichere Verbindung fehlgeschlagen: Bitte HTTPS-Zertifikat und Serveradresse prüfen.':
      'Secure connection failed: please check the HTTPS certificate and the server address.',
  'Adresse: {0}':
      'Address: {0}',
  'Port: {0}':
      'Port: {0}',
  'Server nicht erreichbar: Netzwerk, Serveradresse oder VPN/Tailscale-Verbindung prüfen.\nDiagnose: {0}':
      'Server not reachable: check the network, the server address or the VPN/Tailscale connection.\nDiagnosis: {0}',
  'Netzwerkfehler bei der HTTP-Verbindung: {0}':
      'Network error on the HTTP connection: {0}',
  'Der Server hat eine ungültige Antwort gesendet. Bitte später erneut versuchen.':
      'The server sent an invalid answer. Please try again later.',
  'Verbindung fehlgeschlagen.\nDiagnose: {0} · {1}':
      'Connection failed.\nDiagnosis: {0} · {1}',
  'Ladecockpit {0} ist verfügbar (installiert: {1}).':
      'Ladecockpit {0} is available (installed: {1}).',
  'Später':
      'Later',
  'Download-Seite: {0}':
      'Download page: {0}',
  'Update laden':
      'Get update',
  'Noch kein erfolgreicher Abruf':
      'No successful fetch yet',
  '{0}.{1}.{2}, {3}:{4} Uhr':
      '{2}-{1}-{0}, {3}:{4}',
  'Serververbindung':
      'Server connection',
  'Eine Serveradresse ist auf diesem Gerät hinterlegt.':
      'A server address is stored on this device.',
  'Hinterlege die Adresse deines Ladecockpit-Servers.':
      'Enter the address of your Ladecockpit server.',
  'SERVERZUGRIFF':
      'SERVER ACCESS',
  'Serveradresse':
      'Server address',
  'Adresse mit Port, z. B. über Tailscale oder im Heimnetz':
      'Address with port, e.g. over Tailscale or in your home network',
  'ANMELDUNG':
      'SIGN-IN',
  'App-Passwort':
      'App password',
  'Optional – nur wenn dein Server ein Passwort verlangt':
      'Optional – only if your server asks for a password',
  'Nach Updates suchen':
      'Check for updates',
  'Fragt beim Start bei GitHub nach der neuesten Version. Es werden keine Ladedaten übertragen.':
      'Asks GitHub for the newest version at start. No charging data is sent.',
  'Die Zugangsdaten werden geschützt auf diesem Gerät gespeichert. Die Verbindung erfolgt direkt zu deinem Server.':
      'The credentials are stored protected on this device. The app connects directly to your server.',
  'Abbrechen':
      'Cancel',
  'Speichern & verbinden':
      'Save & connect',
  'Zuhause geladen':
      'Charged at home',
  '{0} kWh':
      '{0} kWh',
  '{0} €/kWh':
      '{0} €/kWh',
  '{0} km/Tag':
      '{0} km/day',
  '{0} km':
      '{0} km',
  '{0} kW':
      '{0} kW',
  '{0} %/Tag':
      '{0} %/day',
  '{0} €/100 km':
      '{0} €/100 km',
  '{0} kWh/100 km':
      '{0} kWh/100 km',
  '{0} Tage':
      '{0} days',
  'Ja':
      'Yes',
  'Nein':
      'No',
  'MultiPass':
      'MultiPass',
  'Supercharger':
      'Supercharger',
  'Kosten':
      'Costs',
  'Datum unbekannt':
      'Date unknown',
  '{0}.{1}.{2} · {3}:{4} Uhr':
      '{2}-{1}-{0} · {3}:{4}',
  'Alle Monate':
      'All months',
  'Alle Netzwerke':
      'All networks',
  'Alle Standorte':
      'All sites',
  'Ladevorgänge':
      'Sessions',
  'Alle Zeiträume':
      'All periods',
  'Filter':
      'Filter',
  'Aktiv':
      'Active',
  'Zeitraum':
      'Period',
  'Netzwerk':
      'Network',
  'Standort':
      'Site',
  'Filter zurücksetzen':
      'Reset filters',
  'Keine Ladevorgänge für diese Filter gefunden.':
      'No sessions found for these filters.',
  'Unbekannter Standort':
      'Unknown site',
  'Energie':
      'Energy',
  ' · Rechnung vorhanden':
      ' · invoice available',
  'Es werden die ersten 50 Treffer angezeigt.':
      'The first 50 results are shown.',
  '{0} Std. {1} Min.':
      '{0} h {1} min',
  '{0} Min.':
      '{0} min',
  'Beginn':
      'Start',
  'Ende':
      'End',
  'Ladedauer':
      'Duration',
  'Geladene Energie':
      'Energy charged',
  ' kWh':
      ' kWh',
  'Gesamtkosten':
      'Total costs',
  'Ladekosten':
      'Charging costs',
  'Standgebühren':
      'Idle fees',
  'Gutschrift':
      'Credit',
  'Preis pro kWh':
      'Price per kWh',
  ' {0}/kWh':
      ' {0}/kWh',
  'Effektivpreis (berechnet)':
      'Effective price (calculated)',
  'Durchschnittsleistung':
      'Average power',
  ' kW':
      ' kW',
  'Start-Ladestand':
      'Battery at start',
  'Betreiber':
      'Operator',
  'Adresse':
      'Address',
  'Ladevorgang':
      'Session',
  'Schließen':
      'Close',
  'Geladen':
      'Charged',
  'Rechnung vorhanden':
      'Invoice available',
  'ZEITRAUM':
      'PERIOD',
  'ENERGIE UND KOSTEN':
      'ENERGY AND COSTS',
  'STANDORT':
      'SITE',
  'Für diesen Ladevorgang ist keine Rechnung hinterlegt.':
      'There is no invoice for this session.',
  'Rechnung öffnen':
      'Open invoice',
  'Historische Durchschnittswerte aus deinen erfassten Ladevorgängen – keine Live-Tarife.':
      'Historic averages from your recorded sessions – no live tariffs.',
  'Preisradar':
      'Price radar',
  'Günstigste Ladezeit':
      'Cheapest time to charge',
  'Günstigster Standort':
      'Cheapest site',
  'Standort · {0}':
      'Site · {0}',
  'Tarif nach Ladezeit':
      'Price by time of day',
  'Zeitfenster':
      'Time slot',
  ' · Günstigste Zeit':
      ' · cheapest time',
  'Deine häufigsten Ladestandorte':
      'Your most frequent charging sites',
  '{0} Ladestandorte':
      '{0} charging sites',
  'Durchschnittspreise und Ladehäufigkeit':
      'Average prices and how often you charge there',
  ' · Günstigster':
      ' · cheapest',
  'Preiswerte basieren auf den erfassten Rechnungsdaten und sind keine Live-Tarife.':
      'Prices are based on the recorded invoice data and are no live tariffs.',
  'Ladecockpit – Rechnungen {0}':
      'Ladecockpit – invoices {0}',
  'Ladecockpit Rechnungen {0}':
      'Ladecockpit invoices {0}',
  'Jahresübersicht · {0}':
      'Year overview · {0}',
  'Monatsbericht · {0}':
      'Month report · {0}',
  'JAHRESÜBERSICHT':
      'YEAR OVERVIEW',
  'MONATSAUSWERTUNG':
      'MONTH REPORT',
  'Deine Ladekosten im Jahr':
      'Your charging costs of the year',
  'Dein Ladebericht':
      'Your charging report',
  'Seite':
      'page',
  'Seiten':
      'pages',
  'Seite konnte nicht geladen werden.':
      'The page could not be loaded.',
  'CSV-Export':
      'CSV export',
  '{0}{1} Zeilen insgesamt':
      '{0}{1} lines in total',
  'Ladecockpit – Ladevorgänge als CSV':
      'Ladecockpit – sessions as CSV',
  'Ladecockpit CSV-Export':
      'Ladecockpit CSV export',
  'CSV teilen / speichern':
      'Share / save CSV',
  'Kostenentwicklung':
      'Cost development',
  '{0} Monate':
      '{0} months',
  'Letzter Monat':
      'Last month',
  'Monatsdurchschnitt':
      'Monthly average',
  'über {0} Monate':
      'over {0} months',
  'nicht erfasst':
      'not recorded',
  'Preis nicht hinterlegt':
      'no price set',
  '{0}{1} € ({2}{3} %) gegenüber Vormonat':
      '{0}{1} € ({2}{3} %) compared with the month before',
  'Vormonat ohne erfasste Kosten – kein Prozentvergleich':
      'Month before without recorded costs – no percentage comparison',
  '{0} kWh · {1} öffentliche Ladevorgänge':
      '{0} kWh · {1} public sessions',
  'Öffentlich: {0} € · Zuhause: {1}\nEnergie: öffentlich {2} kWh · zuhause {3}':
      'Public: {0} € · Home: {1}\nEnergy: public {2} kWh · home {3}',
  'Öffentlich':
      'Public',
  'Zuhause · erfasste Kosten':
      'Home · recorded costs',
  'Nicht erfasste Heimladekosten werden nicht als 0 € gewertet. Balken zeigen nur bekannte Kosten; Vergleiche berücksichtigen nur die erfassten Beträge.':
      'Home charging costs that were not recorded do not count as 0 €. Bars show known costs only; comparisons use only the recorded amounts.',
  'Berichte & Export':
      'Reports & export',
  'Ladehistorie exportieren':
      'Export charging history',
  'Alle Ladevorgänge als CSV für Excel':
      'All sessions as CSV for Excel',
  'Jahresübersicht {0}':
      'Year overview {0}',
  'Eine Zeile je Monat, z. B. für Steuer oder Arbeitgeber':
      'One line per month, e.g. for tax or your employer',
  'MONATSBERICHTE':
      'MONTH REPORTS',
  '{0} Ladevorgänge · {1}':
      '{0} sessions · {1}',
  '{0} € erfasste Kosten':
      '{0} € recorded costs',
  'Rechnungen als ZIP teilen':
      'Share invoices as ZIP',
  'Monatsbericht ansehen':
      'View month report',
  'Sobald Monatsdaten vorhanden sind, erscheinen deine Berichte hier.':
      'Your reports appear here as soon as there is data for a month.',
  'Monatsbericht öffnen oder die zugehörigen Rechnungen gesammelt teilen.':
      'Open the month report or share its invoices in one file.',
  'Rechnung · {0}':
      'Invoice · {0}',
  'LADERECHNUNG':
      'CHARGING INVOICE',
  'PDF-Seite konnte nicht geladen werden.':
      'The PDF page could not be loaded.',
  'LETZTER BEKANNTER STAND':
      'LAST KNOWN STATE',
  'LIVE-FAHRZEUGDATEN':
      'LIVE VEHICLE DATA',
  'AKKUSTAND':
      'BATTERY LEVEL',
  'Wird geladen':
      'Charging',
  'Lädt derzeit nicht':
      'Not charging right now',
  'Ladestatus nicht verfügbar':
      'Charging state not available',
  'FAHRZEUGSTATUS':
      'VEHICLE STATUS',
  'Dein Ladecockpit':
      'Your Ladecockpit',
  'LÄDT':
      'CHARGING',
  'BATTERIE':
      'BATTERY',
  'REICHWEITE':
      'RANGE',
  'Ladelimit {0} %':
      'Charge limit {0} %',
  'Stand · {0}':
      'As of · {0}',
  'Voraussichtlich fertig · {0}':
      'Expected to finish · {0}',
  'Ladegeschwindigkeit · {0} % pro Stunde':
      'Charging speed · {0} % per hour',
  'Keine Fahrzeugdaten':
      'No vehicle data',
  'Fahrzeugdaten live':
      'Vehicle data live',
  'Letzter Stand':
      'Last known state',
  'Einrichtung fehlt':
      'Setup missing',
  'Verbunden':
      'Connected',
  'Nicht verbunden':
      'Not connected',
  'Tesla-Zugang muss zuerst auf dem Ladecockpit-Server eingerichtet werden.':
      'The Tesla access has to be set up on the Ladecockpit server first.',
  'Der Tesla-Zugang ist eingerichtet, aktuell besteht aber keine Verbindung.':
      'The Tesla access is set up, but there is no connection right now.',
  'Nicht eingerichtet · optional':
      'Not set up · optional',
  'Nicht erreichbar':
      'Not reachable',
  'Home Assistant ist eingerichtet, antwortet aktuell aber nicht.':
      'Home Assistant is set up but does not answer right now.',
  'Verbindung prüfen':
      'Check connection',
  'Alles verbunden':
      'All connected',
  'Verbindungen':
      'Connections',
  'Tesla':
      'Tesla',
  'Status aktualisieren':
      'Refresh status',
  'Tesla-Fehler: {0}':
      'Tesla error: {0}',
  'Home Assistant':
      'Home Assistant',
  'Home-Assistant-Fehler: {0}':
      'Home Assistant error: {0}',
  'Letzte Synchronisation':
      'Last sync',
  'Letzter erfolgreicher App-Abruf':
      'Last successful fetch by the app',
  'Nächste Synchronisation':
      'Next sync',
  'Hinweis: {0}':
      'Note: {0}',
  'Ladevorgänge diesen Monat':
      'Sessions this month',
  'Gesamtkosten diesen Monat':
      'Total costs this month',
  'Unterwegs geladen':
      'Charged on the road',
  'Ø Preis unterwegs':
      'Avg price on the road',
  ' €/kWh':
      ' €/kWh',
  'Wird aktualisiert':
      'Refreshing',
  'Aktualisieren':
      'Refresh',
  'Verbindung':
      'Connection',
  'Daten werden aktualisiert':
      'Refreshing data',
  'Daten geladen':
      'Data loaded',
  'Letzter Stand · {0}':
      'Last known state · {0}',
  'Aktualisiert · {0}':
      'Updated · {0}',
  'Verbindung nicht möglich':
      'Cannot connect',
  'Keine Verbindung zum Server':
      'No connection to the server',
  'Aktualisierung fehlgeschlagen':
      'Refresh failed',
  'Du siehst den letzten Stand, den dein Handy gespeichert hat. {0}':
      'You see the last figures your phone has kept. {0}',
  'Die zuletzt geladenen Daten bleiben sichtbar. {0}':
      'The figures loaded last stay visible. {0}',
  'Erneut versuchen':
      'Try again',
  'Verbindung einrichten':
      'Set up connection',
  'Lade dein Cockpit':
      'Loading your cockpit',
  'Fahrzeug- und Ladedaten werden sicher vom Server abgerufen.':
      'Vehicle and charging data are fetched securely from the server.',
  'MONATSÜBERBLICK':
      'MONTH OVERVIEW',
  'Ladeaktivität und Kosten auf einen Blick':
      'Charging activity and costs at a glance',
  'Für diesen Monat liegen noch keine Kennzahlen vor.':
      'There are no figures for this month yet.',
  'Letzter Ladevorgang':
      'Last session',
  'Gesamt':
      'Total',
  'Ladeprognose':
      'Charging forecast',
  'Fahrzeug':
      'Vehicle',
  'Die Daten kommen direkt von deinem eigenen Ladecockpit.':
      'The data comes directly from your own Ladecockpit.',
  'Ladeaktivität':
      'Charging activity',
  'Deine Ladevorgänge':
      'Your sessions',
  'Finde frühere Ladungen und filtere nach Zeitraum, Ladenetz oder Standort.':
      'Find earlier sessions and filter by period, network or site.',
  'Noch keine Ladevorgänge':
      'No sessions yet',
  'Sobald dein Ladecockpit Ladevorgänge erfasst hat, erscheinen sie hier.':
      'Sessions appear here as soon as your Ladecockpit has recorded some.',
  'Kosten & Überblick':
      'Costs & overview',
  'Deine Auswertungen':
      'Your reports',
  'Behalte Ladepreise, Kostenentwicklung und deine Monatsberichte im Blick.':
      'Keep an eye on charging prices, cost development and your month reports.',
  'Noch nicht verbunden':
      'Not connected yet',
  'Richte die Verbindung zu deinem Ladecockpit ein, um Fahrzeugstatus, Ladevorgänge und Kosten hier zu sehen.':
      'Set up the connection to your Ladecockpit to see vehicle status, sessions and costs here.',
  'Cockpit':
      'Cockpit',
  'Auswertung':
      'Reports',
  'Anmeldung fehlgeschlagen. Bitte App-Passwort und Zugriffsrechte prüfen.':
      'Sign-in failed. Please check the app password and access rights.',
  '{0} konnte nicht geladen werden (HTTP {1}).':
      'Could not load {0} (HTTP {1}).',
  'Ungültige Antwort für {0}.':
      'Invalid answer for {0}.',
  'Akkustand':
      'Battery level',
  'Reichweite':
      'Range',
  'Stand von':
      'As of',
  'Akku-Untergrenze':
      'Battery floor',
  'Ladelimit':
      'Charge limit',
  'Anzahl':
      'Count',
  'Reine Ladekosten':
      'Charging costs only',
  'Durchschnittspreis':
      'Average price',
  'Durchschnittliche Ladeleistung':
      'Average charging power',
  'Gutschriften':
      'Credits',
  'Ladenetz':
      'Network',
  'Voraussichtlicher Ladestopp':
      'Expected charging stop',
  'Prognose':
      'Forecast',
  'Tage bis zur Untergrenze':
      'Days until the floor',
  'Akkuverlust pro Tag':
      'Battery used per day',
  'Strecke pro Tag':
      'Distance per day',
  'Mögliche Ersparnis':
      'Possible saving',
  'Empfohlener Standort':
      'Recommended site',
  'Empfohlenes Datum':
      'Recommended date',
  'Modell':
      'Model',
  'Ausstattung':
      'Trim',
  'Farbe':
      'Colour',
  'Felgen':
      'Wheels',
  'Fahrzeug-ID':
      'Vehicle ID',
  'Baureihe':
      'Generation',
  'Reichweite bei 100 %':
      'Range at 100 %',
  'Veränderung':
      'Change',
  'Seit':
      'Since',
  'Messwerte':
      'Readings',
  'Supercharger-Anteil':
      'Supercharger share',
  'Kosten pro 100 km':
      'Costs per 100 km',
  'Verbrauch pro 100 km':
      'Consumption per 100 km',
  'Gefahrene Strecke':
      'Distance driven',
  'Ersparnis gegenüber Verbrenner':
      'Saving compared with a combustion car',
  'Vergleichbare Spritkosten':
      'Comparable fuel costs',
  'Bezeichnung':
      'Label',
  'Preis zur besten Ladezeit':
      'Price at the best time',
  'Preis am günstigsten Standort':
      'Price at the cheapest site',
  'Januar':
      'January',
  'Februar':
      'February',
  'März':
      'March',
  'April':
      'April',
  'Mai':
      'May',
  'Juni':
      'June',
  'Juli':
      'July',
  'August':
      'August',
  'September':
      'September',
  'Oktober':
      'October',
  'November':
      'November',
  'Dezember':
      'December',
  'Auswertungen':
      'Reports',
  'Ort oder Betreiber suchen':
      'Search place or operator',
  'App sperren':
      'Lock the app',
  'Fragt beim Öffnen nach Fingerabdruck, Gesicht oder der Geräte-PIN.':
      'Asks for fingerprint, face or the phone\'s PIN when the app opens.',
  'Ladecockpit entsperren':
      'Unlock Ladecockpit',
  'Ladecockpit ist gesperrt':
      'Ladecockpit is locked',
  'Entsperren':
      'Unlock',
  'Hier lädst du am günstigsten':
      'Where you charge cheapest',
  'Ladezeit · noch keine Ladevorgänge':
      'Time of day · no sessions yet',
  'Ladezeit · {0}':
      'Time of day · {0}',
  'Standort · noch keine Ladevorgänge':
      'Site · no sessions yet',
  '1 Ladevorgang':
      '1 session',
  '{0} Ladevorgänge':
      '{0} sessions',
  'noch wenig aussagekräftig':
      'too few to tell',
  'Günstigster Standort: {0} €/kWh':
      'Cheapest site: {0} €/kWh',
  '{0} · {1} · {2}{3}':
      '{0} · {1} · {2}{3}',
  ' (nur {0})':
      ' (only {0})',
};
