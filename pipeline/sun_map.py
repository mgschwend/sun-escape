"""Daily sunshine map for Switzerland from MeteoSwiss ICON-CH1-EPS (control run), param DURSUN.

DURSUN is sunshine duration in seconds, accumulated since the run start (DURSUN(run, run) = 0).
A day D (04:00Z..20:00Z) is stitched from a chain of runs: every stretch between two run start times comes from
the run that started at its beginning (fresh 0-3 h forecast), the rest of the day from the newest run.
    sun = sum over stretches [a, b] of DURSUN(r, b) - DURSUN(r, a),  r = newest run started at or before a
Checked 2026-11-10: a single 03Z run said 0 h for Winterthur while the day turned sunny (later runs: 2.6 h).
ICON-CH1 forecasts 33 h ahead, so every run since D-1 11Z reaches D 20Z.
Output per day: site/data/sunmap-YYYY-MM-DD.png (yellow, alpha = hours / FULL_H) + sunmap.json index.

Usage: .venv/bin/python pipeline/sun_map.py [--days 2]
"""
import argparse, json, pathlib, sys, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import eccodes
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://data.geo.admin.ch/api/stac/v1"
COLL = "ch.meteoschweiz.ogd-forecasting-icon-ch1"
BBOX = (5.90, 45.78, 10.55, 47.84)   # lon0, lat0, lon1, lat1
STEP = 0.01                          # deg; ICON-CH1 cells are ~1 km
FULL_H = 9.0                         # full yellow = sun from sunrise to sunset in Nov (my call, see doc)
DAY_START_Z, DAY_END_Z = 4, 20       # brackets sunrise..sunset all year
CACHE = ROOT / "data/grib"


def post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def control_items(valid):
    """Control-run DURSUN items valid at `valid`, newest run first."""
    d = post(f"{API}/search", {"collections": [COLL], "limit": 100,
                               "datetime": valid.strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "query": {"title": {"startsWith": "DURSUN at"}}})
    items = [f for f in d["features"] if not f["properties"]["forecast:perturbed"]]
    return sorted(items, key=lambda f: f["properties"]["forecast:reference_datetime"], reverse=True)


def fetch(item):
    asset = next(iter(item["assets"].values()))
    name = asset["href"].split("?")[0].rsplit("/", 1)[-1]
    path = CACHE / name
    if not path.exists():
        urllib.request.urlretrieve(asset["href"], path)
    return path


def read_values(path):
    with open(path, "rb") as f:
        h = eccodes.codes_grib_new_from_file(f)
        try:
            return eccodes.codes_get_values(h)
        finally:
            eccodes.codes_release(h)


def regrid_index():
    """Nearest ICON cell for every output pixel (cached as .npy, built once from the grid constants)."""
    idx_path = CACHE / f"regrid-ch1-{STEP}.npy"
    if idx_path.exists():
        return np.load(idx_path)
    const = CACHE / "hconst-ch1.grib2"
    if not const.exists():
        with urllib.request.urlopen(f"{API}/collections/{COLL}", timeout=60) as r:
            href = json.load(r)["assets"]["horizontal_constants_icon-ch1-eps.grib2"]["href"]
        urllib.request.urlretrieve(href, const)
    lon = lat = None
    with open(const, "rb") as f:
        while (h := eccodes.codes_grib_new_from_file(f)) is not None:
            sn = eccodes.codes_get(h, "shortName")
            if sn == "tlon": lon = eccodes.codes_get_values(h)
            if sn == "tlat": lat = eccodes.codes_get_values(h)
            eccodes.codes_release(h)
    k = np.cos(np.radians(46.8))
    tree = cKDTree(np.c_[lon * k, lat])
    xs = np.arange(BBOX[0] + STEP / 2, BBOX[2], STEP)
    ys = np.arange(BBOX[3] - STEP / 2, BBOX[1], -STEP)      # north at the top
    gx, gy = np.meshgrid(xs, ys)
    dist, idx = tree.query(np.c_[gx.ravel() * k, gy.ravel()], distance_upper_bound=0.02)
    idx = np.where(np.isfinite(dist), idx, -1).reshape(gy.shape).astype(np.int32)
    np.save(idx_path, idx)
    return idx


def day_map(day, idx):
    end_t = datetime(day.year, day.month, day.day, DAY_END_Z, tzinfo=timezone.utc)
    start_t = end_t.replace(hour=DAY_START_Z)
    iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    runs = sorted({parse(f["properties"]["forecast:reference_datetime"]) for f in control_items(end_t)})
    if not runs:
        return None
    by_valid = {}
    def dursun(run, valid):
        if valid == run:
            return 0.0
        if valid not in by_valid:
            by_valid[valid] = control_items(valid)
        item = next((f for f in by_valid[valid] if f["properties"]["forecast:reference_datetime"] == iso(run)), None)
        if item is None:
            sys.exit(f"{day}: DURSUN missing for run {iso(run)} valid {iso(valid)}")
        return read_values(fetch(item))
    covers_from = max(start_t, runs[0])
    bounds = [covers_from] + [r for r in runs if covers_from < r < end_t] + [end_t]
    sun_s, used = 0.0, []
    for a, b in zip(bounds, bounds[1:]):
        r = max(x for x in runs if x <= a)
        sun_s = sun_s + (dursun(r, b) - dursun(r, a))
        used.append(r.strftime("%d %HZ"))
    run = runs[-1]
    hours = np.clip(sun_s / 3600.0, 0, None)
    grid = np.where(idx >= 0, hours[np.clip(idx, 0, None)], np.nan)
    rgba = np.zeros(grid.shape + (4,), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = 244, 180, 0
    rgba[..., 3] = np.nan_to_num(np.clip(grid / FULL_H, 0, 1) * 255).astype(np.uint8)
    out = ROOT / f"site/data/sunmap-{day}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(out, optimize=True)
    return {"date": str(day), "png": out.name, "run_utc": run.strftime("%Y-%m-%dT%H:%MZ"), "runs_used": used,
            "covers_from_utc": covers_from.strftime("%Y-%m-%dT%H:%MZ"),
            "max_h": round(float(np.nanmax(grid)), 1), "mean_h": round(float(np.nanmean(grid)), 2),
            "kb": round(out.stat().st_size / 1024, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=2)
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    idx = regrid_index()
    today = datetime.now(ZoneInfo("Europe/Zurich")).date()   # runner clock is UTC
    maps = [m for m in (day_map(today + timedelta(d), idx) for d in range(args.days)) if m]
    index = {"source": "MeteoSwiss ICON-CH1-EPS control run, DURSUN", "bbox": BBOX, "step_deg": STEP,
             "full_yellow_h": FULL_H, "maps": maps}
    (ROOT / "site/data/sunmap.json").write_text(json.dumps(index, indent=1))
    for m in maps:
        print(m)


if __name__ == "__main__":
    main()
