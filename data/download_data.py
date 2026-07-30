"""Download every weather/climate input for the site into ./data/.

Run:  python data/download_data.py

Site coordinates come from model.py so there is exactly one place to change
them. Five files are written, matching the schemas the loaders in model.py
expect:

  tmy.json           PVGIS typical meteorological year, hourly (T, GHI, DNI, DHI, wind)
  horizon.json       PVGIS DEM-calculated horizon profile (terrain shading)
  archive.json       Open-Meteo ERA5 daily mean T, 2015-2025 (observed baseline)
  climate.json       Open-Meteo CMIP6-HighRes daily mean T, 2026-2050, 3 models
  climate_minmax.json  same, daily max/min -> separate day & night warming trends

PVGIS is rate-limited (~30 calls/s, but be polite) and occasionally returns 5xx;
each request is retried a few times with a backoff.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from model import LAT, LON  # noqa: E402  (site definition lives in model.py)

# CMIP6-HighRes models available on Open-Meteo that cover the whole 2026-2050 span.
CLIMATE_MODELS = "EC_Earth3P_HR,MRI_AGCM3_2_S,MPI_ESM1_2_XR"

PVGIS = "https://re.jrc.ec.europa.eu/api/v5_2"


def fetch(url, params, tries=4, pause=3.0):
    """GET url?params and return the parsed JSON, retrying on transient errors."""
    full = f"{url}?{urllib.parse.urlencode(params)}"
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "ferme-energy-model"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            detail = ""
            if isinstance(e, urllib.error.HTTPError):
                try:
                    detail = " -- " + e.read().decode("utf-8", "replace")[:300]
                except Exception:
                    pass
            print(f"    attempt {attempt}/{tries} failed: {e}{detail}")
            if attempt == tries:
                raise
            time.sleep(pause * attempt)


def save(name, obj):
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    print(f"    -> {name}  ({os.path.getsize(path) / 1024:.0f} kB)")


def main():
    print(f"site: {LAT:.4f} N, {LON:.4f} E\n")

    print("[1/5] PVGIS TMY (hourly typical meteorological year)")
    tmy = fetch(f"{PVGIS}/tmy", dict(lat=LAT, lon=LON, outputformat="json",
                                     usehorizon=1, browser=0))
    n = len(tmy["outputs"]["tmy_hourly"])
    loc = tmy["inputs"]["location"]
    print(f"    {n} hours, PVGIS elevation {loc['elevation']:.0f} m, "
          f"radiation db {tmy['inputs']['meteo_data']['radiation_db']}")
    save("tmy.json", tmy)

    print("[2/5] PVGIS horizon profile")
    hor = fetch(f"{PVGIS}/printhorizon", dict(lat=LAT, lon=LON, outputformat="json",
                                              browser=0))
    prof = hor["outputs"]["horizon_profile"]
    print(f"    {len(prof)} azimuths, max horizon {max(p['H_hor'] for p in prof):.1f} deg")
    save("horizon.json", hor)

    print("[3/5] Open-Meteo ERA5 archive, daily mean T 2015-2025")
    arc = fetch("https://archive-api.open-meteo.com/v1/archive",
                dict(latitude=LAT, longitude=LON,
                     start_date="2015-01-01", end_date="2025-12-31",
                     daily="temperature_2m_mean", timezone="Europe/Zurich"))
    print(f"    {len(arc['daily']['time'])} days, grid elevation {arc['elevation']:.0f} m")
    save("archive.json", arc)

    print("[4/5] Open-Meteo CMIP6-HighRes, daily mean T 2026-2050")
    clim = fetch("https://climate-api.open-meteo.com/v1/climate",
                 dict(latitude=LAT, longitude=LON,
                      start_date="2026-01-01", end_date="2050-12-31",
                      models=CLIMATE_MODELS, daily="temperature_2m_mean"))
    print(f"    {len(clim['daily']['time'])} days, "
          f"{len([k for k in clim['daily'] if k != 'time'])} model series")
    save("climate.json", clim)

    print("[5/5] Open-Meteo CMIP6-HighRes, daily max/min T 2026-2050")
    mm = fetch("https://climate-api.open-meteo.com/v1/climate",
               dict(latitude=LAT, longitude=LON,
                    start_date="2026-01-01", end_date="2050-12-31",
                    models=CLIMATE_MODELS,
                    daily="temperature_2m_max,temperature_2m_min"))
    print(f"    {len(mm['daily']['time'])} days, "
          f"{len([k for k in mm['daily'] if k != 'time'])} model series")
    save("climate_minmax.json", mm)

    print("\ndone.")


if __name__ == "__main__":
    main()
