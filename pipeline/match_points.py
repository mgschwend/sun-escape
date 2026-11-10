"""Suggest the nearest MeteoSwiss local-forecast point for each spot (prints a review table)."""
import csv, io, json, math, sys, pathlib, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
META = ROOT / "data/meta_point.raw.csv"
if not META.exists():
    META.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve("https://data.geo.admin.ch/ch.meteoschweiz.ogd-local-forecasting/ogd-local-forecasting_meta_point.csv", META)
meta = list(csv.DictReader(io.StringIO(META.read_bytes().decode("latin-1")), delimiter=";"))
cfg = json.loads((ROOT/"config/spots.json").read_text())
TYPES = {"1": "station", "2": "zip", "3": "poi"}
def km(a, b, c, d):
    return math.hypot((c-a)*111.3*math.cos(math.radians(b)), (d-b)*111.2)
for s in [cfg["home"], *cfg["spots"]]:
    cands = []
    for p in meta:
        d = km(s["lon"], s["lat"], float(p["point_coordinates_wgs84_lon"]), float(p["point_coordinates_wgs84_lat"]))
        if d < 6:
            dz = float(p["point_height_masl"]) - s["alt"]
            cands.append((d + abs(dz)/150, d, dz, p))
    cands.sort(key=lambda c: c[0])
    print(f"\n{s['name']} ({s['alt']} m)")
    for score, d, dz, p in cands[:3]:
        print(f"   id {p['point_id']:>5} {TYPES[p['point_type_id']]:7} {p['point_name'][:28]:28} {float(p['point_height_masl']):6.0f} m  {d:4.1f} km  Δz {dz:+5.0f}")
