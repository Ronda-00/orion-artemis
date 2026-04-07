# Eyebit Tracker v1.3 — Orion Artemis II + Satellites

Real-time tracking program for the Orion spacecraft (NASA Artemis II mission) and low-Earth orbit satellites, with graphical interface.

**Author:** EA5EMA - ( Ronda )

## Installation

Requires Python 3.8+ and the following libraries:

```
pip install ephem requests
```

To run:

```bash
python3 seguimiento_orion_montura.py
```

## First step: set your position

Open the program, go to the configuration panel on the right side, section **"Geographic Position"**, and enter:

- **Latitude** in decimal degrees (e.g. 39.49242)
- **Longitude** in decimal degrees (negative for west, e.g. -1.30556)
- **Elevation** in meters above sea level
- **Place** — any name (e.g. "Home", "School"). This name shows on the world map tooltip when you hover over your position. If left empty, the Maidenhead locator is shown instead.
- **Locator** — Maidenhead grid square. You can type it here and press the button to auto-calculate lat/lon, or the other way around.

Press **"Guardar"** (Save) to store the configuration.

You can also choose whether times are displayed in **UTC** or **local time**.

## The polar chart

The large circular plot in the center. It represents the sky as seen from your position:

- The **center** is the zenith (straight above your head, 90° elevation)
- The **outer edge** is the horizon (0° elevation)
- **North** at the top, **East** to the right, **South** at the bottom, **West** to the left
- Concentric circles mark 30° and 60° elevation

Drawn on the chart:

- **Selected satellite or spacecraft trajectory** — dashed line with 3 labeled points:
  - **Rise point** (↑): on the horizon, with azimuth and time
  - **Maximum elevation** (▲): highest point of the pass, with elevation and time
  - **Set point** (↓): on the horizon, with azimuth and time
- **Sun trajectory** — yellow (or blue when Orion is selected). Only shown when the Sun is above the horizon. Same 3 points: rise, max, set.
- **Moon trajectory** — gray. Only shown when the Moon is above the horizon. Same 3 points.
- **Current position** of the Sun and Moon as dots on their trajectory.

Labels never overlap each other or the trajectory lines, thanks to an intelligent placement system that searches for free space across 24 directions.

Hovering the mouse over any trajectory shows a tooltip with azimuth, elevation and time.

Clickable rectangles in the bottom-right corner toggle Orion, Moon and Sun trajectory visibility.

## The world map

Below the polar chart, a flat-projection world map shows:

- **Your position** as a dot (hover to see the place name you configured)
- **Each satellite** as a dot with a letter (A, B, C...). Hover to see the name.
- **The Sun** as a yellow dot (or blue when Orion is selected)
- **The Moon** as a gray dot (or a crescent shape when Orion is selected, to distinguish it from the spacecraft)
- **Orion** as a yellow dot when selected

The map updates every 10 seconds. Clicking a satellite on the map selects it.

## How Orion (Artemis II) tracking works

Orion is on a cislunar trajectory — it does not orbit the Earth like a regular satellite. Therefore **it cannot be computed using TLEs** (which only model Earth orbits with a single gravitational body).

Instead, the program queries the **NASA JPL Horizons API** over the internet:

- URL: `https://ssd.jpl.nasa.gov/api/horizons.api`
- Target ID: **-1024** (Orion Artemis II spacecraft identifier in the Horizons catalog)
- The program sends your geographic coordinates and requests azimuth/elevation every 1 minute
- Horizons returns positions computed with multi-body ephemeris (Earth + Moon + Sun gravity)
- 36 hours of data are queried (12h before now + 24h after) to capture the complete pass
- The program finds the pass containing the current time and draws only that arc
- Data is automatically refreshed every 10 minutes

When you select Orion from the list, the program automatically detects it as a cislunar object and switches from TLE mode to Horizons mode.

## Regular satellites (LEO)

For regular satellites (ISS, SO-50, FO-29, etc.):

- Computed locally using the **PyEphem** library with the SGP4 propagator
- Orbital data is read from the `mis_satelites.tle` file in standard 3-line TLE format
- On startup, the program **automatically updates TLEs** from Celestrak
- Computes all passes for the next 48 hours and displays them in a table
- Navigate between passes with the ◀ ▶ buttons

## Time simulator

The right panel has a section to manually enter a date and time. Useful for testing how the sky looks at any moment:

- Enable the simulator checkbox
- Enter date (DD/MM/YYYY) and time (HH:MM)
- Time is interpreted as UTC or local depending on your configuration
- Press "Aplicar hora" (Apply time)
- **All data recalculates**: satellite trajectories, Sun, Moon, Orion, world map
- The clock bar shows "SIM" and time stops advancing
- Disabling the simulator returns to real time and recalculates everything

## TLE file

The file `mis_satelites.tle` contains the satellites shown in the list. Format:

```
ISS (ZARYA)
1 25544U 98067A   26096.00498673  .00007825  00000+0  15107-3 0  9998
2 25544  51.6327 297.3095 0006349 277.1679  82.8588 15.48794122560566
```

Add or remove satellites by editing this file.

## Artemis II frequencies (for radio amateurs)

- S-band downlink: 2210.5 MHz, 2287.5 MHz, 2290.8 MHz
- Voice and telemetry are encrypted — cannot be decoded
- What you can do: see the carrier on a waterfall display and measure Doppler shift
