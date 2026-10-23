# Changelog

## 0.2.0 – 2026-10-23

- **Runs as a Home Assistant app**: install it from this repository in Home Assistant, the web app opens from the sidebar. No separate server or PC needed.
- Charging power (average kW) per session and per site.
- kWh per 100 km/mi (billed energy incl. charging losses) per month.
- Export: all sessions as CSV, all invoices of a month as a ZIP file.
- Notification in Home Assistant when the Tesla sign-in expired or syncing keeps failing (event `ladecockpit_problem`).
- On a fresh install the battery level, range and odometer are taken from the Home Assistant history, so they show up right away.
- The web app can be added to a phone's home screen with its own icon.
- The container now runs as root (needed for the Home Assistant app).

## 0.1.0 – 2026-10-23

First public version.

- Fetches Supercharger invoices from the Tesla Fleet API (read-only) and sends each one once to Home Assistant as the event `ladecockpit_invoice`.
- Blueprint to book invoices into your own `input_number` / `input_text` helpers.
- Detects the end of a charging session from a Home Assistant entity and looks for the invoice right away.
- Web app (English/German) with last invoice, monthly cost, cost per 100 km/mi, price radar by time of day and site, next charging stop forecast, reconciliation with Home Assistant totals, Tesla API usage.
- Keeps its own history of battery level and odometer, so the last value stays visible while the car is offline.
- Demo mode without credentials.
