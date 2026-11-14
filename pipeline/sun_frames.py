"""Hourly sunshine frames for the animated map, from MeteoSwiss ICON-CH1/CH2 control run, param DURSUN.

Frame t = sunshine in the hour (t-1h, t] (UTC):  DURSUN(r, t) - DURSUN(r, t-1h),
r = newest run of the model that started at or before t-1h (freshest forecast for that hour; DURSUN(r, r) = 0).
Model per frame: ICON-CH1 (1 km) if it has t, else ICON-CH2 (2 km), else the frame is skipped.
Frames per day: hours ending FIRST_END_Z .. DAY_END_Z[month] (UTC), i.e. daylight only.
Output: site/data/sunh-YYYYMMDDHH.png (yellow, alpha = minutes / 60) + sunframes.json.

Usage: .venv/bin/python pipeline/sun_frames.py [--days 5]
"""
import argparse, json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image

from sun_map import BBOX, CACHE, DAY_END_Z, MODELS, ROOT, control_items, fetch, read_values, regrid_index

# end hour (UTC) of the first frame per month: the hour containing the earliest sunrise in Switzerland
FIRST_END_Z = {1: 7, 2: 7, 3: 6, 4: 5, 5: 4, 6: 4, 7: 4, 8: 5, 9: 5, 10: 6, 11: 7, 12: 7}
H = timedelta(hours=1)
iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
_items = {}


def items(model, valid):
    key = (model["key"], valid)
    if key not in _items:
        _items[key] = control_items(model, valid)
    return _items[key]


def dursun(model, run, valid):
    if valid == run:
        return 0.0
    it = next((f for f in items(model, valid) if f["properties"]["forecast:reference_datetime"] == iso(run)), None)
    return None if it is None else read_values(fetch(it))


def frame(t):
    for model in MODELS:
        runs = sorted(parse(f["properties"]["forecast:reference_datetime"]) for f in items(model, t))
        runs = [r for r in runs if r <= t - H]
        if runs:
            break
    else:
        return None
    r = runs[-1]
    a, b = dursun(model, r, t - H), dursun(model, r, t)
    if a is None or b is None:
        return None
    minutes = np.clip((b - a) / 60.0, 0, 60)
    idx = regrid_index(model)
    grid = np.where(idx >= 0, minutes[np.clip(idx, 0, None)], np.nan)
    rgba = np.zeros(grid.shape + (4,), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = 244, 180, 0
    rgba[..., 3] = np.nan_to_num(grid / 60 * 255).astype(np.uint8)
    out = ROOT / f"site/data/sunh-{t:%Y%m%d%H}.png"
    Image.fromarray(rgba, "RGBA").save(out, optimize=True)
    return {"end_utc": t.strftime("%Y-%m-%dT%H:%MZ"), "png": out.name, "model": f"ICON-{model['key'].upper()}",
            "res_km": model["res_km"], "run_utc": r.strftime("%d %HZ"),
            "mean_min": round(float(np.nanmean(grid)), 1), "kb": round(out.stat().st_size / 1024, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5)
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    for old in (ROOT / "site/data").glob("sunh-*.png"):
        old.unlink()
    today = datetime.now(ZoneInfo("Europe/Zurich")).date()
    frames = []
    for d in range(args.days):
        day = today + timedelta(d)
        for h in range(FIRST_END_Z[day.month], DAY_END_Z[day.month] + 1):
            f = frame(datetime(day.year, day.month, day.day, h, tzinfo=timezone.utc))
            if f:
                frames.append(f)
    (ROOT / "site/data/sunframes.json").write_text(json.dumps(
        {"source": "MeteoSwiss ICON-CH1-EPS / ICON-CH2-EPS control run, DURSUN per hour", "bbox": BBOX,
         "frames": frames}, indent=1))
    kb = sum(f["kb"] for f in frames)
    print(f"{len(frames)} frames, {kb / 1024:.1f} MB, first {frames[0]['end_utc']}, last {frames[-1]['end_utc']}")
    print("models:", {m: sum(f['model'] == m for f in frames) for m in ("ICON-CH1", "ICON-CH2")})


if __name__ == "__main__":
    main()
