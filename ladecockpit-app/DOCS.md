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

Import the blueprint `blueprints/automation/ladecockpit/book_invoice.yaml` from the repository. It adds every invoice to your helpers and can send a notification.

## Comparison with a combustion car

Enter the consumption (L/100 km) and fuel price of a comparison car, either as fixed values or as entities (e.g. the average consumption of your other car and a fuel price sensor). Ladecockpit then shows what the same distance would have cost and what you saved, per month and projected for a year.

## More options

- **Charging at home**: the energy meter of your wallbox (kWh, only increasing) and your electricity price, fixed or from an entity such as a dynamic tariff. The price at the time of charging is used.
- **Outside temperature**: a sensor or a weather entity, for the consumption by temperature.

## Sensors

Ladecockpit creates its own entities: `sensor.ladecockpit_next_charge`, `sensor.ladecockpit_battery`, `sensor.ladecockpit_month_cost`, `sensor.ladecockpit_last_charge`, `sensor.ladecockpit_price_tip`, `sensor.ladecockpit_range_at_100`, `sensor.ladecockpit_consumption`, `sensor.ladecockpit_car` (a picture of your car, chosen in the web app with **Customise**), `sensor.ladecockpit_multipass` (third-party stations where MultiPass has worked for you, with map links) and `binary_sensor.ladecockpit_problem`. Use them in dashboards and automations. A ready-made dashboard section is in `homeassistant/dashboard_card.yaml` in the repository. Turn this off with **Create sensors in Home Assistant**.

These entities have no unique ID, so they cannot be renamed in the UI. After a Home Assistant restart they are back within a few minutes.

## Problems

If the Tesla sign-in expires or syncing keeps failing, Ladecockpit creates a notification in Home Assistant and fires the event `ladecockpit_problem`. You can turn this off with **Notify about problems**.
