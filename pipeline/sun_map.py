"""Daily sunshine maps for Switzerland from MeteoSwiss ICON-CH1-EPS / ICON-CH2-EPS (control run), param DURSUN.

DURSUN is sunshine duration in seconds, accumulated since the run start (DURSUN(run, run) = 0).
A day D (DAY_START_Z .. sunset cut-off, UTC) is stitched from a chain of runs: every stretch between two run start
times comes from the run that started at its beginning (fresh short-range forecast), the rest from the newest run.
    sun = sum over stretches [a, b] of DURSUN(r, b) - DURSUN(r, a),  r = newest run started at or before a
Checked 2026-11-10: a single 03Z run said 0 h for Winterthur while the day turned sunny (later runs: 2.6 h).

Model per day: ICON-CH1 (1 km, 33 h ahead, runs every 3 h) if one of its runs reaches the day's cut-off,
else ICON-CH2 (2 km, 120 h ahead, runs every 6 h), else no map for that day.
Output per day: site/data/sunmap-YYYY-MM-DD.png (yellow, alpha = hours / FULL_H) + sunmap.json index.

Usage: .venv/bin/python pipeline/sun_map.py [--days 9]
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
BBOX = (5.90, 45.78, 10.55, 47.84)   # lon0, lat0, lon1, lat1
FULL_H = 9.0                         # full yellow = sun from sunrise to sunset in Nov (my call, see doc)
DAY_START_Z = 3                      # before the earliest sunrise (Jun ~03:30Z)
# hour (UTC) after the latest sunset in Switzerland that month; later cut-offs only cost forecast reach
DAY_END_Z = {1: 17, 2: 17, 3: 18, 4: 19, 5: 20, 6: 20, 7: 20, 8: 20, 9: 19, 10: 18, 11: 17, 12: 17}
MODELS = [  # tried in order
    {"key": "ch1", "coll": "ch.meteoschweiz.ogd-forecasting-icon-ch1", "step": 0.01, "res_km": 1, "reach": 0.02},
    {"key": "ch2", "coll": "ch.meteoschweiz.ogd-forecasting-icon-ch2", "step": 0.02, "res_km": 2, "reach": 0.04},
]
CACHE = ROOT / "data/grib"


def post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def control_items(model, valid):
    """Control-run DURSUN items of `model` valid at `valid` (STAC item datetime = valid time)."""
    d = post(f"{API}/search", {"collections": [model["coll"]], "limit": 100,
                               "datetime": valid.strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "query": {"title": {"startsWith": "DURSUN at"}}})
    return [f for f in d["features"] if not f["properties"]["forecast:perturbed"]]


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


def regrid_index(model):
    """Nearest ICON cell for every output pixel (cached as .npy, built once from the model's grid constants)."""
    step = model["step"]
    idx_path = CACHE / f"regrid-{model['key']}-{step}.npy"
    if idx_path.exists():
        return np.load(idx_path)
    const = CACHE / f"hconst-{model['key']}.grib2"
    if not const.exists():
        with urllib.request.urlopen(f"{API}/collections/{model['coll']}", timeout=60) as r:
            href = json.load(r)["assets"][f"horizontal_constants_icon-{model['key']}-eps.grib2"]["href"]
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
    xs = np.arange(BBOX[0] + step / 2, BBOX[2], step)
    ys = np.arange(BBOX[3] - step / 2, BBOX[1], -step)      # north at the top
    gx, gy = np.meshgrid(xs, ys)
    dist, idx = tree.query(np.c_[gx.ravel() * k, gy.ravel()], distance_upper_bound=model["reach"])
    idx = np.where(np.isfinite(dist), idx, -1).reshape(gy.shape).astype(np.int32)
    np.save(idx_path, idx)
    return idx


def day_sun(model, day):
    """Stitched sunshine seconds per model cell for `day`, or None if no run of `model` reaches the cut-off."""
    end_t = datetime(day.year, day.month, day.day, DAY_END_Z[day.month], tzinfo=timezone.utc)
    start_t = end_t.replace(hour=DAY_START_Z)
    iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    runs = sorted({parse(f["properties"]["forecast:reference_datetime"]) for f in control_items(model, end_t)})
    if not runs:
        return None
    by_valid = {}
    def dursun(run, valid):
        if valid == run:
            return 0.0
        if valid not in by_valid:
            by_valid[valid] = control_items(model, valid)
        item = next((f for f in by_valid[valid] if f["properties"]["forecast:reference_datetime"] == iso(run)), None)
        if item is None:
            sys.exit(f"{day} {model['key']}: DURSUN missing for run {iso(run)} valid {iso(valid)}")
        return read_values(fetch(item))
    covers_from = max(start_t, runs[0])
    bounds = [covers_from] + [r for r in runs if covers_from < r < end_t] + [end_t]
    sun_s, used = 0.0, []
    for a, b in zip(bounds, bounds[1:]):
        r = max(x for x in runs if x <= a)
        sun_s = sun_s + (dursun(r, b) - dursun(r, a))
        used.append(r.strftime("%d %HZ"))
    return {"sun_s": sun_s, "runs": runs, "used": used, "covers_from": covers_from, "end": end_t}


def day_map(day):
    for model in MODELS:
        res = day_sun(model, day)
        if res is not None:
            break
    else:
        return None
    idx = regrid_index(model)
    hours = np.clip(res["sun_s"] / 3600.0, 0, None)
    grid = np.where(idx >= 0, hours[np.clip(idx, 0, None)], np.nan)
    rgba = np.zeros(grid.shape + (4,), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = 244, 180, 0
    rgba[..., 3] = np.nan_to_num(np.clip(grid / FULL_H, 0, 1) * 255).astype(np.uint8)
    out = ROOT / f"site/data/sunmap-{day}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(out, optimize=True)
    fmt = lambda t: t.strftime("%Y-%m-%dT%H:%MZ")
    return {"date": str(day), "png": out.name, "model": f"ICON-{model['key'].upper()}", "res_km": model["res_km"],
            "run_utc": fmt(res["runs"][-1]), "runs_used": res["used"],
            "covers_utc": [fmt(res["covers_from"]), fmt(res["end"])],
            "max_h": round(float(np.nanmax(grid)), 1), "mean_h": round(float(np.nanmean(grid)), 2),
            "kb": round(out.stat().st_size / 1024, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=9)
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    today = datetime.now(ZoneInfo("Europe/Zurich")).date()   # runner clock is UTC
    maps = [m for m in (day_map(today + timedelta(d)) for d in range(args.days)) if m]
    index = {"source": "MeteoSwiss ICON-CH1-EPS / ICON-CH2-EPS control run, DURSUN", "bbox": BBOX,
             "full_yellow_h": FULL_H, "maps": maps}
    (ROOT / "site/data/sunmap.json").write_text(json.dumps(index, indent=1))
    for m in maps:
        print({k: m[k] for k in ("date", "model", "runs_used", "covers_utc", "max_h", "kb")})


if __name__ == "__main__":
    main()
