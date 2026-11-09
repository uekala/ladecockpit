# Ladecockpit Mobile – Automotive Design System

Status: approved visual direction (2026-11-08)

The Home Assistant Ladecockpit dashboard screenshot approved on 2026-11-08 is the visual reference for the mobile app. This document translates that direction into implementation rules. It does not replace product behavior or remove existing features.

## Design principles

- Automotive instrument-cluster feeling: calm, precise, premium and immediately readable.
- Dark-first interface with deep near-black surfaces and restrained emerald/teal highlights.
- Vehicle and battery state are the visual focus; secondary analytics remain easy to scan.
- Use clear German labels, explicit timestamps and honest freshness/offline states.
- Mobile-first layouts with generous touch targets and no horizontal overflow.

## Core color tokens

| Token | Value | Usage |
|---|---|---|
| Background | `#070B10` | Main app background |
| Surface | `#111820` | Primary cards |
| Surface elevated | `#182329` | Nested cards and controls |
| Border | `#27333A` | Subtle card outlines |
| Text primary | `#F2F6FA` | Main values and headings |
| Text secondary | `#8D9AAF` | Metadata and supporting labels |
| Accent green | `#39E6A5` | Live, connected, positive state |
| Accent teal | `#22C9C3` | Battery gauge and interactive highlights |
| Warning | `#F5B85B` | Stale data or attention required |
| Error | `#FF6B70` | Failed operations and connection errors |

## Shape, depth and typography

- Main cards: 24–30 px corner radius, subtle 1 px border and restrained dark gradient.
- Secondary cards: 16–20 px corner radius.
- Avoid heavy shadows and bright large-area fills; glow is reserved for live/active accents.
- Headline values should be large and tabular where possible; metadata should remain legible.
- Section labels use compact uppercase lettering with moderate tracking.
- Keep spacing consistent in 4 px increments; primary card padding 20–24 px.

## Dashboard hierarchy

1. Header with app title, connection/live indicator and a clear refresh action.
2. Vehicle hero card with vehicle name, model/configuration metadata and vehicle image when a valid asset is available.
3. Large battery gauge as the dominant metric, with percentage and estimated range.
4. Explicit data freshness label (live, last known, timestamp) and charging/offline state.
5. Next charging recommendation / forecast.
6. Monthly overview metrics.
7. Last charging session, cost development, price radar, history and exports.

## Gauge and status behavior

- The battery gauge must show the actual state of charge; never use decorative sample values.
- Keep the charging window or configured target visible when the API provides it.
- Live data uses the green/teal accent; cached or stale data uses warning styling and a clear timestamp.
- Offline is a connection/data freshness state, not a substitute for the last known battery value.
- Missing values use a neutral placeholder; do not infer a range or percentage.

## Existing functionality must be preserved

The redesign is presentation-only unless a separately reviewed change is explicitly required. Keep connection setup, secure password storage, Tailscale access, refresh, Tesla and optional Home Assistant status, charging history filters, price radar, cost development, invoice viewing, monthly reports, CSV export and ZIP sharing.

## Accessibility and responsive behavior

- Maintain strong contrast on dark surfaces.
- Do not communicate status by color alone; pair color with text and/or an icon.
- Touch targets should be at least 44 px.
- At narrow widths, stack content rather than compressing text or clipping values.
- Respect system text scaling and avoid fixed-height content cards where text can grow.

## Implementation sequence

1. Introduce centralized theme tokens and shared card styling.
2. Rework the vehicle hero and battery gauge to match the approved reference.
3. Apply the same card, spacing and typography rules to analytics, history and export sections.
4. Verify loading, empty, offline, stale-data and error states.
5. Run Flutter analyze, widget tests and Android release build before review.

No production deployment, live Home Assistant changes, credential changes or merge are part of this design foundation.
