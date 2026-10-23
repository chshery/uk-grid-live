import os, time
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

load_dotenv()
DAYS = 90
CHUNK = 7  # days per API call
OUT = "data/history"
os.makedirs(OUT, exist_ok=True)

END = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
START = END - timedelta(days=DAYS)
FMT = "%Y-%m-%dT%H:%MZ"


def windows():
    s = START
    while s < END:
        e = min(s + timedelta(days=CHUNK), END)
        yield s, e
        s = e


def get(url, params=None):
    for attempt in range(3):
        r = requests.get(url, params=params, timeout=60)
        if r.status_code == 200:
            return r.json()
        time.sleep(3)
    r.raise_for_status()


# ---------- 1. Regional carbon intensity (18 regions, forecast + generation mix)
def backfill_regional():
    rows = []
    for s, e in windows():
        url = f"https://api.carbonintensity.org.uk/regional/intensity/{s.strftime(FMT)}/{e.strftime(FMT)}"
        for period in get(url)["data"]:
            for reg in period["regions"]:
                row = {
                    "period_from": period["from"],
                    "period_to": period["to"],
                    "region_id": reg["regionid"],
                    "region_name": reg["shortname"],
                    "forecast_gco2": reg["intensity"]["forecast"],
                    "intensity_index": reg["intensity"]["index"],
                }
                for g in reg.get("generationmix", []):
                    row[f"mix_{g['fuel']}"] = g["perc"]
                rows.append(row)
        print("regional", s.date(), "->", e.date(), "rows so far:", len(rows))
    df = pd.DataFrame(rows).drop_duplicates(["period_from", "region_id"])
    df.to_csv(f"{OUT}/carbon_regional.csv", index=False)
    return df


# ---------- 2. National carbon intensity (forecast AND actual -> used for forecasting)
def backfill_national():
    rows = []
    for s, e in windows():
        url = f"https://api.carbonintensity.org.uk/intensity/{s.strftime(FMT)}/{e.strftime(FMT)}"
        for p in get(url)["data"]:
            rows.append({
                "period_from": p["from"],
                "period_to": p["to"],
                "ng_forecast_gco2": p["intensity"]["forecast"],
                "actual_gco2": p["intensity"]["actual"],
                "intensity_index": p["intensity"]["index"],
            })
        print("national", s.date(), "->", e.date())
    df = pd.DataFrame(rows).drop_duplicates("period_from")
    df.to_csv(f"{OUT}/carbon_national.csv", index=False)
    return df


# ---------- 3. Octopus Agile prices (14 regions)
REGIONS = list("ABCDEFGHJKLMNP")


def agile_product():
    data = get("https://api.octopus.energy/v1/products/",
               {"brand": "OCTOPUS_ENERGY", "is_variable": "true", "page_size": 100})
    agile = [p for p in data["results"]
             if p["code"].startswith("AGILE") and p.get("direction") == "IMPORT"]
    agile.sort(key=lambda p: p["available_from"], reverse=True)
    print("Using product:", agile[0]["code"])
    return agile[0]["code"]


def backfill_prices():
    product = agile_product()
    rows = []
    for letter in REGIONS:
        tariff = f"E-1R-{product}-{letter}"
        url = f"https://api.octopus.energy/v1/products/{product}/electricity-tariffs/{tariff}/standard-unit-rates/"
        params = {"period_from": START.strftime(FMT), "period_to": END.strftime(FMT), "page_size": 1500}
        while url:
            data = get(url, params)
            for r in data["results"]:
                rows.append({
                    "region_code": letter,
                    "valid_from": r["valid_from"],
                    "valid_to": r["valid_to"],
                    "price_inc_vat_p": r["value_inc_vat"],
                    "price_exc_vat_p": r["value_exc_vat"],
                })
            url, params = data.get("next"), None  # 'next' already contains the params
        print("prices region", letter, "done, rows so far:", len(rows))
    df = pd.DataFrame(rows).drop_duplicates(["region_code", "valid_from"])
    df.to_csv(f"{OUT}/agile_prices.csv", index=False)
    return df


# ---------- 4. Upload to Azure Blob (raw/history/)
def upload():
    svc = BlobServiceClient.from_connection_string(os.environ["AZURE_STORAGE_CONNECTION_STRING"])
    container = svc.get_container_client("raw")
    for f in os.listdir(OUT):
        with open(f"{OUT}/{f}", "rb") as fh:
            container.upload_blob(f"history/{f}", fh, overwrite=True)
        print("uploaded history/" + f)


if __name__ == "__main__":
    r = backfill_regional()
    n = backfill_national()
    p = backfill_prices()
    print("\nSUMMARY")
    print("regional carbon:", len(r), "rows")
    print("national carbon:", len(n), "rows")
    print("agile prices:   ", len(p), "rows")
    upload()