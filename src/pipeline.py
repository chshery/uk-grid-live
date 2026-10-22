import json
import os
from datetime import datetime, timedelta, timezone

import requests
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

CARBON_API = "https://api.carbonintensity.org.uk"
OCTOPUS_API = "https://api.octopus.energy/v1"
OCTOPUS_REGIONS = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P"]

service = BlobServiceClient.from_connection_string(os.environ["AZURE_STORAGE_CONNECTION_STRING"])
container = service.get_container_client("raw")


def upload(name, data):
    container.upload_blob(name=name, data=json.dumps(data), overwrite=True)
    print("Uploaded:", name)


def fetch_carbon(now):
    r = requests.get(f"{CARBON_API}/regional", headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    upload(f"carbon/date={now:%Y-%m-%d}/regional_{stamp}.json", r.json())


def find_agile_product():
    r = requests.get(f"{OCTOPUS_API}/products/", params={"is_variable": "true", "brand": "OCTOPUS_ENERGY"}, timeout=30)
    r.raise_for_status()
    codes = [p["code"] for p in r.json()["results"] if p["code"].startswith("AGILE")]
    return sorted(codes)[-1]


def fetch_prices(now):
    product = find_agile_product()
    period_from = (now - timedelta(days=1)).strftime("%Y-%m-%dT00:00Z")
    period_to = (now + timedelta(days=2)).strftime("%Y-%m-%dT00:00Z")
    for region in OCTOPUS_REGIONS:
        tariff = f"E-1R-{product}-{region}"
        url = f"{OCTOPUS_API}/products/{product}/electricity-tariffs/{tariff}/standard-unit-rates/"
        r = requests.get(url, params={"period_from": period_from, "period_to": period_to, "page_size": 1500}, timeout=30)
        r.raise_for_status()
        upload(f"prices/date={now:%Y-%m-%d}/agile_{region}.json", r.json())


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    fetch_carbon(now)
    fetch_prices(now)
    print("Pipeline finished at", now.isoformat())