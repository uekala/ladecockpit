# Ladecockpit

Ladecockpit fetches your real Supercharger invoices from the Tesla Fleet API and reports each new one to Home Assistant as the event `ladecockpit_invoice`. The web app opens from the sidebar.

## Before you start

- You need a Tesla developer app with Fleet API access. If you use the Tesla Fleet integration, you can reuse its app.
- In that app on developer.tesla.com, add `http://localhost:8077/auth/callback` to **Allowed Redirect URIs** and enable the scope **Vehicle Charging Management**.
- **Run only one Ladecockpit.** If it already runs elsewhere (Docker on a PC or server), stop it first. Two instances would report every invoice twice.

## Configuration

1. Enter **Tesla client ID** and **Tesla client secret**.
2. Enter the entities of your car. They are all optional, and each one unlocks a feature:
   - **Battery level**, e.g. `sensor.my_tesla_battery_level`: battery card and charging forecast.
   - **Range**: shown next to the battery level.
   - **Odometer**: distance, cost and kWh per 100 km/mi.
   - **Charging state**, e.g. `sensor.my_tesla_charging`: the invoice is fetched right after a session ends.
   - **Charging power** and **Time to full**, e.g. `sensor.my_tesla_charger_power` and `sensor.my_tesla_time_to_full_charge`: while the car charges, the web app shows the power and when the charge limit is reached.
3. Optional: the two `input_number` helpers the blueprint books into. They enable the "HA vs. invoices" check.
4. Start the app and open **Ladecockpit** in the sidebar.

## Connect to Tesla

1. Click **Sign in with Tesla**. Tesla opens in a new tab.
2. After signing in, Tesla redirects to `http://localhost:8077/auth/callback?code=…`. That page does not load, which is expected.
3. Copy the full address from the browser bar of that tab and paste it into the field in Ladecockpit.

The first sync starts right away. Invoices from before are only imported and **not** reported, so totals you already keep are not counted twice.

## Booking invoices

Import the blueprint `blueprints/automation/ladecockpit/book_invoice.yaml` from the repository. It adds every invoice to your helpers and can send a notification. If you only want the notification, import `blueprints/automation/ladecockpit/notify_invoice.yaml` instead or in addition; it needs no helpers.

## Comparison with a combustion car

Enter the consumption (L/100 km) and fuel price of a comparison car, either as fixed values or as entities (e.g. the average consumption of your other car and a fuel price sensor). Ladecockpit then shows what the same distance would have cost and what you saved, per month and projected for a year.

## More options

- **Charging at home**: the energy meter of your wallbox (kWh, only increasing) and your electricity price, fixed or from an entity such as a dynamic tariff. The price at the time of charging is used.
- **Outside temperature**: a sensor or a weather entity, for the consumption by temperature.

## Backup and year overview

In the web app, **Connections & API costs** has **Download backup** and **Restore backup**: charging history, readings and invoices in one file, without the Tesla sign-in. Restoring replaces the charging history; sessions already reported to Home Assistant are not booked twice. After moving to another Home Assistant, sign in with Tesla once.

Under **Export** you find a **year overview** as PDF for every year with sessions: one line per month with sessions, kWh, net, VAT, gross and credits.

## Sensors

Ladecockpit creates its own entities: `sensor.ladecockpit_next_charge`, `sensor.ladecockpit_battery`, `sensor.ladecockpit_month_cost`, `sensor.ladecockpit_last_charge`, `sensor.ladecockpit_price_tip`, `sensor.ladecockpit_range_at_100`, `sensor.ladecockpit_consumption`, `sensor.ladecockpit_car` (a picture of your car, chosen in the web app with **Customise**), `sensor.ladecockpit_multipass` (third-party stations where MultiPass has worked for you, with map links) and `binary_sensor.ladecockpit_problem`. Use them in dashboards and automations. A ready-made dashboard section is in `homeassistant/dashboard_card.yaml` in the repository. Turn this off with **Create sensors in Home Assistant**.

These entities have no unique ID, so they cannot be renamed in the UI. After a Home Assistant restart they are back within a few minutes.

## Problems

If the Tesla sign-in expires or syncing keeps failing, Ladecockpit creates a notification in Home Assistant and fires the event `ladecockpit_problem`. You can turn this off with **Notify about problems**.

## Network access and security

The sidebar uses Home Assistant Ingress and is authenticated by Home Assistant. The optional `8077/tcp` port bypasses Ingress; leave it disabled unless you need direct access, for example for the [mobile app](https://github.com/uekala/ladecockpit/blob/main/mobile/README.md). Direct access stays locked until you set **Mobile app password**: set it first, restart the app, and only then map the port. The mobile app signs in with this password. Restrict the port to a trusted private network or VPN such as Tailscale, or put it behind a reverse proxy that requires authentication and HTTPS. Do not publish it directly to the internet. The standalone `APP_PASSWORD` requirement does not apply to the Ingress-only Home Assistant app.
