import json
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://api.octopus.energy/v1"
OUT = Path("data/raw/prices")
OUT.mkdir(parents=True, exist_ok=True)


def find_agile_product():
    r = requests.get(f"{BASE}/products/", params={"is_variable": "true", "brand": "OCTOPUS_ENERGY"}, timeout=30)
    r.raise_for_status()
    codes = [p["code"] for p in r.json()["results"] if p["code"].startswith("AGILE")]
    return sorted(codes)[-1]


def fetch_agile_rates(product, region="G"):
    tariff = f"E-1R-{product}-{region}"
    url = f"{BASE}/products/{product}/electricity-tariffs/{tariff}/standard-unit-rates/"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    product = find_agile_product()
    print("Current Agile product:", product)

    data = fetch_agile_rates(product, region="G")  # G = North West England
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT / f"agile_G_{stamp}.json"
    path.write_text(json.dumps(data, indent=2))

    print(f"Saved {path}  ({len(data['results'])} half-hour prices)")
    for p in data["results"][:5]:
        print(f"  {p['valid_from']}  {p['value_inc_vat']:.2f}p/kWh")