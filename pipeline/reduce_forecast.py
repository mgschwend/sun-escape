"""Reduce the latest MeteoSwiss local forecast (sunshine, ~30 MB, all ~5800 points)
to a small spots.json for Winterthur and the curated spots.

Source: MeteoSwiss OGD local forecasting, param sre000h0 (sunshine duration, hourly total, minutes, UTC).
Usage: python3 pipeline/reduce_forecast.py [--out site/data/spots.json]
"""
import argparse, csv, io, json, pathlib, sys, time, urllib.request
from collections import defaultdict
from datetime import datetime, timezone

STAC = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-local-forecasting"
PARAM = "sre000h0"
ROOT = pathlib.Path(__file__).resolve().parent.parent


def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def latest_asset():
    """Newest sunshine file: items are one per day; pick the latest run inside the newest day that has one."""
    items = get_json(f"{STAC}/items?limit=10")["features"]
    for item in sorted(items, key=lambda f: f["id"], reverse=True):
        assets = get_json(f"{STAC}/items/{item['id']}")["assets"]
        runs = sorted(k for k in assets if k.endswith(f".{PARAM}.csv"))
        if runs:
            return runs[-1], assets[runs[-1]]["href"]
    sys.exit("no sunshine file found in the latest items")


def stream_rows(url, wanted):
    """Stream the CSV line by line, keep only wanted point ids. Never holds the whole file."""
    out = defaultdict(list)
    with urllib.request.urlopen(url, timeout=300) as r:
        reader = csv.reader(io.TextIOWrapper(r, encoding="latin-1", newline=""), delimiter=";")
        header = next(reader)
        assert header[:3] == ["point_id", "point_type_id", "Date"] and header[3] == PARAM, header
        for pid, ptype, date, val in reader:
            if (pid, ptype) in wanted:
                out[(pid, ptype)].append((date, int(val) if val else None))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "site/data/spots.json"))
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config/spots.json").read_text())
    places = [cfg["home"], *cfg["spots"]]
    # point_id alone is NOT unique (89 ids repeat across point types) -> key on (id, type)
    wanted = {(str(p["point_id"]), str(p["point_type_id"])) for p in places}

    name, url = latest_asset()
    t0 = time.time()
    rows = stream_rows(url, wanted)
    missing = wanted - rows.keys()
    if missing:
        sys.exit(f"point ids not in forecast file: {sorted(missing)}")

    def series(p):
        r = sorted(rows[(str(p["point_id"]), str(p["point_type_id"]))])
        dates = [d for d, _ in r]
        assert len(dates) == len(set(dates)), f"duplicate timestamps for {p['name']}"
        return {"start_utc": r[0][0], "sun_min": [v for _, v in r]}

    run = name.split(".")[2]  # e.g. 202611101700
    doc = {
        "source": "MeteoSwiss local forecast (OGD), sre000h0",
        "run_utc": run,
        "file": name,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "interval": "value at timestamp t = sunshine minutes in the hour ending at t (UTC); checked: summit sunrise/sunset hours on 2026-11-14",
        "home": {**cfg["home"], **series(cfg["home"])},
        "spots": [{**s, **series(s)} for s in cfg["spots"]],
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    print(f"{name}: {len(rows)} points, {len(doc['home']['sun_min'])} h each, "
          f"{time.time() - t0:.0f} s, wrote {out} ({out.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
