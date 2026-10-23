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
3. Optional: the two `input_number` helpers the blueprint books into. They enable the "HA vs. invoices" check.
4. Start the app and open **Ladecockpit** in the sidebar.

## Connect to Tesla

1. Click **Sign in with Tesla**. Tesla opens in a new tab.
2. After signing in, Tesla redirects to `http://localhost:8077/auth/callback?code=…`. That page does not load, which is expected.
3. Copy the full address from the browser bar of that tab and paste it into the field in Ladecockpit.

The first sync starts right away. Invoices from before are only imported and **not** reported, so totals you already keep are not counted twice.

## Booking invoices

Import the blueprint `blueprints/automation/ladecockpit/book_invoice.yaml` from the repository. It adds every invoice to your helpers and can send a notification.

## Problems

If the Tesla sign-in expires or syncing keeps failing, Ladecockpit creates a notification in Home Assistant and fires the event `ladecockpit_problem`. You can turn this off with **Notify about problems**.
