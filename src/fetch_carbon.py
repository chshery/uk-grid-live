import json
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://api.carbonintensity.org.uk"
OUT = Path("data/raw/carbon")
OUT.mkdir(parents=True, exist_ok=True)


def fetch_regional_now():
    response = requests.get(f"{BASE}/regional", headers={"Accept": "application/json"}, timeout=30)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    data = fetch_regional_now()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT / f"regional_{stamp}.json"
    path.write_text(json.dumps(data, indent=2))

    regions = data["data"][0]["regions"]
    print(f"Saved {path}  ({len(regions)} regions)")
    for r in regions[:5]:
        print(f"  {r['shortname']:<25} {r['intensity']['forecast']:>4} gCO2/kWh  ({r['intensity']['index']})")