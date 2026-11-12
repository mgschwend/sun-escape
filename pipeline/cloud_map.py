"""Daytime low-cloud maps (fog / Hochnebel proxy) from MeteoSwiss ICON-CH1/CH2 control run, param CLCL.

CLCL = low cloud cover in % at the valid time (instantaneous). A day's map is the mean of SAMPLE_Z hours (UTC);
each sample comes from the newest run valid at that time. Model per day: ICON-CH1 if it has the day's last
sample, else ICON-CH2, else no map (same rule as sun_map.py).
Output: site/data/lowcloud-YYYY-MM-DD.png (grey, alpha = cover) + lowcloud.json (incl. % at home and spots).

Usage: .venv/bin/python pipeline/cloud_map.py [--days 5]
"""
import argparse, json, pathlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image

from sun_map import API, BBOX, CACHE, MODELS, ROOT, fetch, post, read_values, regrid_index

SAMPLE_Z = [8, 10, 12, 14]          # ~09-15 local in winter: the hours a day trip cares about
RGB = (70, 88, 118)               # slate blue: must stand out from the grey map base


def control_items(model, param, valid):
    d = post(f"{API}/search", {"collections": [model["coll"]], "limit": 100,
                               "datetime": valid.strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "query": {"title": {"startsWith": f"{param} at"}}})
    return [f for f in d["features"] if not f["properties"]["forecast:perturbed"]]


def day_map(day, places):
    times = [datetime(day.year, day.month, day.day, h, tzinfo=timezone.utc) for h in SAMPLE_Z]
    for model in MODELS:
        if control_items(model, "CLCL", times[-1]):
            break
    else:
        return None
    vals, runs = [], []
    for t in times:
        items = control_items(model, "CLCL", t)
        if not items:
            return None
        newest = max(items, key=lambda f: f["properties"]["forecast:reference_datetime"])
        runs.append(newest["properties"]["forecast:reference_datetime"][8:13].replace("T", " ") + "Z")
        vals.append(read_values(fetch(newest)))
    cover = np.clip(np.mean(vals, axis=0), 0, 100)
    idx = regrid_index(model)
    grid = np.where(idx >= 0, cover[np.clip(idx, 0, None)], np.nan)
    rgba = np.zeros(grid.shape + (4,), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = RGB
    rgba[..., 3] = np.nan_to_num(grid / 100 * 235).astype(np.uint8)
    out = ROOT / f"site/data/lowcloud-{day}.png"
    Image.fromarray(rgba, "RGBA").save(out, optimize=True)
    step = model["step"]
    def at(lon, lat):
        r, c = int((BBOX[3] - lat) / step), int((lon - BBOX[0]) / step)
        return round(float(grid[r, c]))
    return {"date": str(day), "png": out.name, "model": f"ICON-{model['key'].upper()}", "res_km": model["res_km"],
            "samples_utc": [f"{h:02d}Z" for h in SAMPLE_Z], "runs_used": runs,
            "mean_pct": round(float(np.nanmean(grid)), 1), "kb": round(out.stat().st_size / 1024, 1),
            "places": {p["name"]: at(p["lon"], p["lat"]) for p in places}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5)
    args = ap.parse_args()
    cfg = json.loads((ROOT / "config/spots.json").read_text())
    places = [cfg["home"]] + cfg["spots"]
    today = datetime.now(ZoneInfo("Europe/Zurich")).date()
    maps = [m for m in (day_map(today + timedelta(d), places) for d in range(args.days)) if m]
    (ROOT / "site/data/lowcloud.json").write_text(json.dumps(
        {"source": "MeteoSwiss ICON-CH1-EPS / ICON-CH2-EPS control run, CLCL (low cloud cover, %)",
         "bbox": BBOX, "maps": maps}, indent=1))
    for m in maps:
        print({k: m[k] for k in ("date", "model", "runs_used", "mean_pct", "kb")}, m["places"])


if __name__ == "__main__":
    main()
