# Changelog

## 0.4.0 – 2026-10-23

- **MultiPass**: sessions at third-party chargers paid through Tesla MultiPass are recognised in the Tesla charging history and shown separately (session list, sites, month, price comparison). The event `ladecockpit_invoice`, the blueprint and `sensor.ladecockpit_last_charge` carry `network` (`supercharger` or `multipass`); `sensor.ladecockpit_month_cost` has `multipass_cost` and `multipass_sessions`. The CSV export has a new last column.
- **Savings vs. a combustion car**: with a consumption and a fuel price (fixed or from entities), the month shows what the distance would have cost with petrol or diesel and what you saved. New options `fuel_consumption`, `entity_fuel_consumption`, `fuel_price`, `entity_fuel_price`.
- **Projection**: cost and distance per year from the last 90 days, with the savings vs. the combustion car.
- **Charging plan**: the next-stop card tells you when and where to charge before the battery reaches the floor – the cheapest Supercharger and time window from your own invoices, with the expected saving (`plan` on `sensor.ladecockpit_next_charge`).
- **Monthly report**: on the first of the month the event `ladecockpit_month_report` with last month's figures and a ready text, plus a notification in Home Assistant (option `month_report`).
- The log notes fields in Tesla's charging history that Ladecockpit does not know yet.

## 0.3.0 – 2026-10-23

- **Sensors in Home Assistant**: Ladecockpit now creates `sensor.ladecockpit_next_charge`, `sensor.ladecockpit_battery`, `sensor.ladecockpit_month_cost`, `sensor.ladecockpit_last_charge`, `sensor.ladecockpit_price_tip` and `binary_sensor.ladecockpit_problem` itself. No YAML needed. Option `publish_entities` / `PUBLISH_ENTITIES`.
- Ready-made dashboard section with built-in cards: `homeassistant/dashboard_card.yaml`.
- The REST sensors in `homeassistant/ladecockpit_package.yaml` are gone. If you copied them, remove them, they would clash with the new entities.

## 0.2.1 – 2026-10-23

- Fix: on a fresh install the battery level, range and odometer were not taken from the Home Assistant history (only the first of the ten days was requested). They now show up right away, also while the car is asleep and its entities are `unknown`.

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
