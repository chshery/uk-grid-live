import os, time
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv()
H = "data/history"

url = URL.create(
    "mssql+pyodbc",
    username=os.environ["SQL_USER"],
    password=os.environ["SQL_PASSWORD"],
    host=f"{os.environ['SQL_SERVER']}.database.windows.net",
    port=1433,
    database=os.environ["SQL_DB"],
    query={"driver": "ODBC Driver 18 for SQL Server", "Encrypt": "yes",
           "TrustServerCertificate": "no", "Connection Timeout": "90"},
)
engine = create_engine(url, fast_executemany=True)


def connect_with_retry():
    # free serverless DB may be paused - first try wakes it up
    for i in range(5):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            print("Connected to Azure SQL")
            return
        except Exception as e:
            print(f"Waking database... attempt {i+1}: {str(e)[:80]}")
            time.sleep(20)
    raise SystemExit("Could not connect")


def run_schema():
    sql = open("sql/01_schema.sql").read()
    with engine.begin() as c:
        for stmt in [s for s in sql.split("GO") if s.strip()]:
            c.exec_driver_sql(stmt)
    print("Schema created")


# carbon region id -> Octopus region letter (1-14 are DNO regions, 15-18 are nations/GB)
REGION_MAP = {1: "P", 2: "N", 3: "G", 4: "F", 5: "M", 6: "D", 7: "K",
              8: "E", 9: "B", 10: "A", 11: "L", 12: "H", 13: "C", 14: "J"}


def key(ts):
    return ts.dt.strftime("%Y%m%d%H%M").astype("int64")


def build():
    reg = pd.read_csv(f"{H}/carbon_regional.csv")
    nat = pd.read_csv(f"{H}/carbon_national.csv")
    pr = pd.read_csv(f"{H}/agile_prices.csv")

    reg["ts"] = pd.to_datetime(reg["period_from"], utc=True)
    nat["ts"] = pd.to_datetime(nat["period_from"], utc=True)
    pr["ts"] = pd.to_datetime(pr["valid_from"], utc=True)

    # dim_region
    dim_region = (reg[["region_id", "region_name"]].drop_duplicates("region_id")
                  .sort_values("region_id"))
    dim_region["octopus_code"] = dim_region["region_id"].map(REGION_MAP)
    dim_region["region_level"] = dim_region["region_id"].apply(lambda r: "region" if r <= 14 else "nation")

    # dim_datetime (from every timestamp we have)
    ts = pd.Series(pd.concat([reg["ts"], nat["ts"], pr["ts"]]).unique())
    ts = pd.to_datetime(ts, utc=True)
    local = ts.dt.tz_convert("Europe/London")
    dim_dt = pd.DataFrame({
        "datetime_key": key(ts),
        "utc_datetime": ts.dt.tz_localize(None),
        "local_datetime": local.dt.tz_localize(None),
        "local_date": local.dt.date,
        "local_hour": local.dt.hour,
        "settlement_period": local.dt.hour * 2 + local.dt.minute // 30 + 1,
        "day_name": local.dt.day_name(),
        "is_weekend": local.dt.dayofweek >= 5,
        "month_name": local.dt.month_name(),
    }).drop_duplicates("datetime_key")

    # fact_grid = regional carbon + price for that region & half hour
    letter_to_id = {v: k for k, v in REGION_MAP.items()}
    pr["region_id"] = pr["region_code"].map(letter_to_id)
    reg = reg.merge(pr[["ts", "region_id", "price_inc_vat_p"]], on=["ts", "region_id"], how="left")
    reg["datetime_key"] = key(reg["ts"])
    mix_cols = ["mix_gas", "mix_coal", "mix_nuclear", "mix_wind", "mix_solar",
                "mix_hydro", "mix_biomass", "mix_imports", "mix_other"]
    reg = reg.reindex(columns=list(reg.columns) + [c for c in mix_cols if c not in reg.columns])
    fact_grid = reg[["datetime_key", "region_id", "forecast_gco2", "intensity_index"]
                    + mix_cols + ["price_inc_vat_p"]].drop_duplicates(["datetime_key", "region_id"])

    # fact_national
    nat["datetime_key"] = key(nat["ts"])
    fact_nat = nat[["datetime_key", "ng_forecast_gco2", "actual_gco2", "intensity_index"]] \
        .drop_duplicates("datetime_key")

    return dim_region, dim_dt, fact_grid, fact_nat


def load(df, name):
    df.to_sql(name, engine, if_exists="append", index=False, chunksize=5000)
    print(f"loaded {name}: {len(df):,} rows")


def checks():
    q = {
        "dim_region": "SELECT COUNT(*) FROM dim_region",
        "dim_datetime": "SELECT COUNT(*) FROM dim_datetime",
        "fact_grid": "SELECT COUNT(*) FROM fact_grid",
        "fact_national": "SELECT COUNT(*) FROM fact_national",
        "regions 1-14 missing price": "SELECT COUNT(*) FROM fact_grid WHERE region_id<=14 AND price_inc_vat_p IS NULL",
        "national missing actual": "SELECT COUNT(*) FROM fact_national WHERE actual_gco2 IS NULL",
    }
    print("\nCHECKS")
    with engine.connect() as c:
        for k, s in q.items():
            print(f"{k}: {c.execute(text(s)).scalar():,}")


if __name__ == "__main__":
    connect_with_retry()
    run_schema()
    dim_region, dim_dt, fact_grid, fact_nat = build()
    load(dim_region, "dim_region")
    load(dim_dt, "dim_datetime")
    load(fact_grid, "fact_grid")
    load(fact_nat, "fact_national")
    checks()