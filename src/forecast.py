import os
import requests
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import text
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error
from load_sql import engine

os.makedirs("docs/images", exist_ok=True)
TEST_DAYS = 14

# ---------- 1. Load national carbon from Azure SQL
q = """
SELECT d.utc_datetime, d.settlement_period, d.day_name, d.is_weekend,
       n.actual_gco2, n.ng_forecast_gco2
FROM fact_national n JOIN dim_datetime d ON d.datetime_key = n.datetime_key
ORDER BY d.utc_datetime
"""
with engine.connect() as c:
    df = pd.read_sql(text(q), c)
df["utc_datetime"] = pd.to_datetime(df["utc_datetime"])
print("Loaded", len(df), "national half-hours")

# ---------- 2. Weather forecasts (Open-Meteo historical forecast API, free, no key)
SITES = {
    "aberdeen":    (57.15, -2.10),   # north-east Scotland wind
    "dogger_bank": (54.75,  1.90),   # biggest offshore wind area
    "irish_sea":   (53.80, -3.60),   # west coast offshore wind
    "midlands":    (52.48, -1.90),   # solar + demand proxy
}
cache = "data/history/weather.csv"
if os.path.exists(cache):
    wx = pd.read_csv(cache, parse_dates=["hour_utc"])
else:
    start = df["utc_datetime"].min().date().isoformat()
    end = df["utc_datetime"].max().date().isoformat()
    frames = []
    for name, (lat, lon) in SITES.items():
        r = requests.get("https://historical-forecast-api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
            "hourly": "wind_speed_100m,shortwave_radiation,temperature_2m",
            "timezone": "GMT"}, timeout=60)
        r.raise_for_status()
        h = r.json()["hourly"]
        f = pd.DataFrame({"hour_utc": pd.to_datetime(h["time"]),
                          f"wind_{name}": h["wind_speed_100m"]})
        if name == "midlands":
            f["solar_rad"] = h["shortwave_radiation"]
            f["temp"] = h["temperature_2m"]
        frames.append(f.set_index("hour_utc"))
        print("weather", name, "ok")
    wx = pd.concat(frames, axis=1).reset_index()
    wx.to_csv(cache, index=False)

df["hour_utc"] = df["utc_datetime"].dt.floor("h")
df = df.merge(wx, on="hour_utc", how="left")
wind_cols = [c for c in df.columns if c.startswith("wind_")]
df["wind_avg"] = df[wind_cols].mean(axis=1)

# ---------- 3. Features (only things known 24h+ before)
df = df.set_index("utc_datetime").sort_index()
df["lag_24h"] = df["actual_gco2"].shift(48)
df["lag_48h"] = df["actual_gco2"].shift(96)
df["lag_7d"] = df["actual_gco2"].shift(336)
df["dow"] = df.index.dayofweek
df["is_weekend"] = df["is_weekend"].astype(int)

FEATURES = ["settlement_period", "dow", "is_weekend", "lag_24h", "lag_48h", "lag_7d",
            "wind_avg", *wind_cols, "solar_rad", "temp"]
data = df.dropna(subset=FEATURES + ["actual_gco2", "ng_forecast_gco2"])

split = data.index.max() - pd.Timedelta(days=TEST_DAYS)
train, test = data[data.index <= split], data[data.index > split]
print(f"Train: {len(train)} rows | Test: {len(test)} rows (last {TEST_DAYS} days)")

# ---------- 4. Model
model = HistGradientBoostingRegressor(max_iter=500, learning_rate=0.05, random_state=42)
model.fit(train[FEATURES], train["actual_gco2"])
test = test.copy()
test["model_forecast"] = model.predict(test[FEATURES]).round(1)

# ---------- 5. Compare
results = {
    "Naive: same time yesterday":      mean_absolute_error(test["actual_gco2"], test["lag_24h"]),
    "Naive: same time last week":      mean_absolute_error(test["actual_gco2"], test["lag_7d"]),
    "My model (24h ahead + weather)":  mean_absolute_error(test["actual_gco2"], test["model_forecast"]),
    "National Grid (updated to delivery)": mean_absolute_error(test["actual_gco2"], test["ng_forecast_gco2"]),
}
print("\nMAE on last 14 days (gCO2/kWh, lower is better)")
for k, v in results.items():
    print(f"  {k:<38} {v:6.1f}")
improve = 1 - results["My model (24h ahead + weather)"] / results["Naive: same time yesterday"]
print(f"\nModel beats 'same time yesterday' by {improve:.0%}")

# ---------- 6. What drives the forecast
imp = permutation_importance(model, test[FEATURES], test["actual_gco2"],
                             n_repeats=5, random_state=42, scoring="neg_mean_absolute_error")
top = pd.Series(imp.importances_mean, index=FEATURES).sort_values(ascending=False).head(5)
print("\nTop 5 drivers:")
for k, v in top.items():
    print(f"  {k:<20} {v:5.1f}")

# ---------- 7. Save results to Azure SQL (for Power BI) + chart
out = test[["actual_gco2", "ng_forecast_gco2", "model_forecast", "lag_24h"]].reset_index()
out.columns = ["utc_datetime", "actual_gco2", "ng_forecast_gco2", "model_forecast_gco2", "naive_24h_gco2"]
out.to_sql("forecast_results", engine, if_exists="replace", index=False)
print("\nSaved forecast_results to Azure SQL:", len(out), "rows")

last7 = out[out["utc_datetime"] > out["utc_datetime"].max() - pd.Timedelta(days=7)]
plt.figure(figsize=(12, 4.5))
plt.plot(last7["utc_datetime"], last7["actual_gco2"], label="Actual", linewidth=2, color="black")
plt.plot(last7["utc_datetime"], last7["model_forecast_gco2"], label="My model (24h ahead)", color="#2ca02c")
plt.plot(last7["utc_datetime"], last7["naive_24h_gco2"], label="Same time yesterday", color="#999999", alpha=0.7)
plt.title("GB carbon intensity: 24-hour-ahead forecast vs actual (last 7 days)")
plt.ylabel("gCO2/kWh"); plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
plt.savefig("docs/images/forecast_vs_actual.png", dpi=150)
print("Saved chart: docs/images/forecast_vs_actual.png")