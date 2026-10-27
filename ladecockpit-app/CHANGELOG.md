# Changelog

## 0.11.0 – 2026-10-27

- **New look: Dynamic.** It replaces *Modern* (whoever used Modern gets Dynamic). A cockpit at night, always dark: the battery is a glowing ring with ticks, the floor and the charge limit, next to the picture of your car. When the page opens, the tiles rise one after the other, the ring draws itself, figures count up and bars grow. The light of the page follows the battery – green, amber when it gets low, red below the floor, cyan while charging – and the time of day. The price radar marks the time slot you are in right now; tap a slot for sessions, kWh and how far it is from your average. Tap or point at a month in the history for its figures. The session list shows the newest six and opens the rest on request. Figures in Saira, text in Geist (both SIL Open Font License, shipped with the app). *Classic* stays as it was and stays the default.
- **Live while charging.** While the car charges, the web app shows *Charging* with the power, when the charge limit is reached and how long that takes, counting down every second. Ladecockpit asks Home Assistant every 15 seconds instead of every minute while the car charges, and the web app refreshes as often. Two new optional entities: *Charging power* (e.g. `sensor.my_tesla_charger_power`) and *Time to full* (e.g. `sensor.my_tesla_time_to_full_charge`, a timestamp or a duration). Without them the finish time is estimated from the power and the kWh one percent takes, or from how fast the battery level rises.
- While the car charges, the next charging stop is counted from the charge limit.
- The demo now shows a car charging at a Supercharger.
- `status` in `/api/dashboard` has `charging`, `power`, `rate` (% per hour) and `finish`. `PUT /api/look` takes `classic` or `dynamic` (`modern` still works and means `dynamic`).

## 0.10.0 – 2026-10-27

- **The fuel price you actually paid.** The combustion-car comparison can use what you really paid per litre instead of a fixed price or a station's current price. Set two new options, *Fuel cost total* and *Litres filled total* – two entities that grow with each fill-up, e.g. the helpers of a fuel log in Home Assistant. Ladecockpit keeps a daily reading of both and uses the average of the last 90 days; until it has 90 days, or after the totals were reset, it uses everything the totals hold. The paid price wins over *Fuel price from an entity* and the fixed fuel price; the month card says "… €/L paid", and a tip shows how many litres the average is based on.
- `compare.fuel` in `/api/dashboard` has `source` (`paid`, `entity` or `fixed`), `paid_days` and `paid_litres`.

## 0.9.0 – 2026-10-27

- **Pick the look: classic or modern.** At the bottom of the web app, *Look* switches between two looks. *Classic* is the look of 0.8, calm and close to the car's own app. *Modern* is new: prices carry the colours of the energy label, from dark green (cheaper than your average) to red (dearer) – the price radar becomes arrows on that scale, sites and sessions show their price colour, and a small scale explains it. Everything else is ink on paper: Bricolage Grotesque with condensed bold figures, a battery bar in 20 segments like a car's display, outlined buttons, tiles with a hairline frame. Dark and light mode follow the device in both looks.
- The choice is saved in Ladecockpit, so every phone and computer shows the same. Classic stays the default.
- Both looks bring their typefaces along (Geist; Bricolage Grotesque). A browser only loads the files of the look in use.
- New API: `PUT /api/look` with `{"look": "classic"}` or `{"look": "modern"}`; `GET /api/dashboard` has `look`.

## 0.8.0 – 2026-10-27

- **New look, calmer and closer to the car's own app.** The car and the battery open the page without a frame: the picture of your car, the battery in large light figures and a slim green battery bar with the charge window marked. Below, flat tiles without borders or shadows, rows with thin separators instead of dotted leaders, plain tabular figures instead of a typewriter face, labels in sentence case. Black in dark mode, white in light mode, blue for actions and bars, green for the battery and the cheapest time slot.
- The month card spans the full width: the total and figures on the left, the comparison lines on the right.
- The typeface (Geist, SIL Open Font License) ships with Ladecockpit, so the page no longer loads fonts from Google.
- On phones the header takes one line less, and the car's name and *Customise* sit side by side.

## 0.7.1 – 2026-10-26

- **Clearer month card.** The lines under the month total are grouped, most useful first: what the total is made of (only with more than one part), the comparison with a combustion car, the check against your reference price, and the fuel of another car – each group separated by a line.
- The combustion-car comparison now says which distance it uses (e.g. "604 km since 16.10." when odometer readings start mid-month) and shows the Tesla cost for that same distance, so *combustion car − Tesla = saved* adds up on the card. Before, the combustion figure could look smaller than the month total although money was saved.

## 0.7.0 – 2026-10-25

- **Slow sessions.** Each session's average power is compared with what your car usually gets at the same Supercharger (the median of your other sessions there with at least 20 kWh). A session with less than 60 % of that is marked in the session list (with the usual value) and on the last-charge card, and a tip names the most recent one with the common reasons: a cold battery without preconditioning, or a shared or throttled stall. Short sessions and sessions that started above 50 % battery are never called slow, because they charge slower on purpose.
- The event `ladecockpit_invoice`, the blueprint and `sensor.ladecockpit_last_charge` carry `avg_power_kw`, `typical_power_kw` and `slow` (the sensor also `start_soc`), e.g. to mention a slow session in the notification.
- The demo has a slow session after a long drive.

## 0.6.2 – 2026-10-25

- **Invoices in the Home Assistant app.** In the Home Assistant companion app on a phone, the PDF links did nothing or ended on a sign-in error: the app has no PDF viewer, and links that open a new window leave the Home Assistant sign-in behind. In the app, *Invoice (PDF)* and the monthly report now open a view inside Ladecockpit with the pages as pictures (tap a page to zoom, back closes it), with a *Download* button that saves the PDF to the phone. The ZIP and CSV exports download the same way. In a normal browser nothing changes.
- New API: `GET /api/invoice/<id>/pages`, `GET /api/invoice/<id>/page/<n>.png` and the same for `/api/report/<YYYY-MM>`. Invoice pages are rendered once and cached next to the PDF.

## 0.6.1 – 2026-10-25

- **Quieter log.** Ladecockpit no longer logs every request to Home Assistant and Tesla (about a dozen lines a minute) or the health check. Warnings and errors still show up, so real problems are easy to spot again.

## 0.6.0 – 2026-10-24

- **Where MultiPass has worked.** A new list of every third-party station where a MultiPass session is on your invoices: operator, sessions, average price, last use and a link that searches the station on Google Maps. The operators are shown as chips, so you see which networks already took MultiPass from you. It only regroups invoices Ladecockpit already has – no extra Tesla requests.
- New entity `sensor.ladecockpit_multipass`: number of those stations as state, the list as attribute `stations` (with `map_url`), plus `operators` and a ready `text`. The ready-made dashboard section shows it once there is a station.
- The demo has a second MultiPass station.

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
