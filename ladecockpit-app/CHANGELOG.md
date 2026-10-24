# Changelog

## 0.5.0 – 2026-10-24

- **Picture of your car.** The web app shows your Tesla, rendered by Tesla's own configurator. Pick model and generation (Model S, 3, X and Y since 2012, Cybertruck), trim (e.g. Performance or Plaid), wheels, paint and view under **Customise**. Only combinations Tesla can render are offered. Without a choice, model and generation are recognised from the VIN.
- New entity `sensor.ladecockpit_car`: the car's name as state, its picture as entity picture, plus `image`, `image_front`, `image_side` and `image_rear` for dashboards. The ready-made dashboard section shows it.
- New API: `GET /api/car`, `POST /api/car/preview`, `PUT /api/car`, `DELETE /api/car`.

## 0.4.1 – 2026-10-23

- New entities `sensor.ladecockpit_range_at_100` (with long-term statistics, for a graph of the battery health over months) and `sensor.ladecockpit_consumption` (billed kWh per 100 km/mi this month, plus the consumption by outside temperature as attribute `by_temperature`).

## 0.4.0 – 2026-10-23

- **MultiPass**: sessions at third-party chargers paid through Tesla MultiPass are recognised in the Tesla charging history and shown separately (session list, sites, month, price comparison). The event `ladecockpit_invoice`, the blueprint and `sensor.ladecockpit_last_charge` carry `network` (`supercharger` or `multipass`); `sensor.ladecockpit_month_cost` has `multipass_cost` and `multipass_sessions`. The CSV export has a new last column.
- **Savings vs. a combustion car**: with a consumption and a fuel price (fixed or from entities), the month shows what the distance would have cost with petrol or diesel and what you saved. New options `fuel_consumption`, `entity_fuel_consumption`, `fuel_price`, `entity_fuel_price`.
- **Projection**: cost and distance per year from the last 90 days, with the savings vs. the combustion car.
- **Charging plan**: the next-stop card tells you when and where to charge before the battery reaches the floor – the cheapest Supercharger and time window from your own invoices, with the expected saving (`plan` on `sensor.ladecockpit_next_charge`).
- **Monthly report**: on the first of the month the event `ladecockpit_month_report` with last month's figures and a ready text, plus a notification in Home Assistant (option `month_report`).
- **Tesla credits**: sessions partly paid with Tesla credits (e.g. free Supercharging with a new car) now show the list price and the credit. Price radar, sites, charging plan and MultiPass comparison use the list price, so a credit no longer makes a Supercharger look cheap. Paid amounts are unchanged. The CSV export has list price, credit and net amount.
- **Charging at home**: optional wallbox energy meter and electricity price (fixed or an entity, priced at the time of charging). Included in the month, cost per 100 km/mi, savings and projection (`entity_home_energy`, `home_price`, `entity_home_price`). `sensor.ladecockpit_month_cost` is now the total incl. charging at home (`invoice_cost`, `home_cost` as attributes).
- **Battery health**: range at 100 % over time and the Supercharger share of the charged energy (`range_at_100` on `sensor.ladecockpit_battery`).
- **Consumption by outside temperature** (`entity_outside_temp`, sensor or weather entity).
- **Monthly PDF** `/api/report/<YYYY-MM>.pdf`: cover sheet with net, VAT, gross and credits, followed by all invoices of the month.
- The log notes fields in Tesla's charging history that Ladecockpit does not know yet.
- Price tips only appear for differences of at least €0.03/kWh.
- Fix: the web app no longer scrolls sideways on narrow phones.

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
