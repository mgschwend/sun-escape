# Sun Escape

Personal dashboard: is Winterthur in a sun drought, and where is the nearest sun reachable by train.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 pipeline/reduce_forecast.py          # ~1 s  -> site/data/spots.json (~10 KB)
.venv/bin/python pipeline/sun_map.py         # ~10 s -> site/data/sunmap-*.png + sunmap.json
python3 -m http.server 8766 -d site          # open http://localhost:8766
```

## Pieces

| File | What |
|---|---|
| `config/spots.json` | 6 curated winter-sun spots (Uetliberg, Bad Ragaz, Chur, Bellinzona, Lugano, Pilatus; why: `docs/winter-sun-spots.md`): coords, MeteoSwiss `point_id` + `point_type_id`, hand-entered travel time, changes, longest seated stretch, last ride down |
| `pipeline/match_points.py` | review table: nearest MeteoSwiss forecast points per spot (all 15 matched within 0.8 km / 66 m) |
| `pipeline/reduce_forecast.py` | streams the newest ~30 MB `sre000h0` CSV, keeps the configured points |
| `pipeline/sun_map.py` | `DURSUN` control run → PNG per day, stitched from a chain of runs: ICON-CH1 (1 km, today + tomorrow), then ICON-CH2 (2 km, up to ~day 5) |
| `site/index.html` | dashboard: banner, 5 day maps in a row (spots coloured by forecast, ring = nearest sun after a 09:30 departure), 9-day strip for Winterthur; reads `data/*.json` |

## Findings (verified 2026-11-10)

- **`point_id` is not unique**: 89 ids repeat across point types (711 = Säntis POI *and* Flühli LU station). Key on `(point_id, point_type_id)`.
- **`sre000h0` at timestamp t = sunshine minutes in the hour ending at t (UTC)**: summit values on 14 Nov are 35 min in 06–07 UTC (sunrise) and 50 min in 15–16 UTC (sunset).
- **The sunshine file is ~30 MB per hourly run and is served uncompressed**, even when gzip is requested.
- **The DURSUN STAC item `datetime` is the valid time**, not the run time. Filter by `forecast:reference_datetime` client-side; the search API only accepts `title`/`created`/... in `query`.
- **A single morning run can be badly wrong on fog days**: the 03Z run gave Winterthur 0 h, but later runs gave 2.6 h. Hence the stitched chain of runs.
- **The local forecast's already-past hours didn't match measurements today**. At 6 SwissMetNet stations the mean error was 1.9 h for the local forecast vs 0.5 h for the stitched map. That's 1 day and 6 stations; the cause is unknown.

## Deploy

`.github/workflows/build.yml` runs every 3 h (minute 35), on push to `main` and on demand. It builds `site/data/` and deploys `site/` to GitHub Pages. Generated data isn't committed. If the repo has been quiet for 45 days, a scheduled run pushes an empty commit, because GitHub disables scheduled workflows after 60 days without activity.

## Not built yet

SwissMetNet "measured today" / last day with ≥ 2 h sun · OJP travel times · fog-top inference.
