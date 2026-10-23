import requests
import pandas as pd
import altair as alt
import streamlit as st
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="UK Grid Live", page_icon="⚡", layout="wide")
UK = "Europe/London"
REGION_TO_LETTER = {1: "P", 2: "N", 3: "G", 4: "F", 5: "M", 6: "D", 7: "K",
                    8: "E", 9: "B", 10: "A", 11: "L", 12: "H", 13: "C", 14: "J"}
APPLIANCES = {"EV charge (4h)": 8, "Dishwasher (2h)": 4, "Washing machine (1.5h)": 3,
              "Tumble dryer (1h)": 2, "Heat pump boost (30m)": 1}


def now_utc():
    t = datetime.now(timezone.utc)
    return t.replace(minute=0 if t.minute < 30 else 30, second=0, microsecond=0)


def outward(postcode):
    p = postcode.strip().upper()
    if " " in p:
        return p.split()[0]
    return p[:-3] if len(p) > 4 else p


@st.cache_data(ttl=1800, show_spinner=False)
def carbon_forecast(outcode):
    start = now_utc().strftime("%Y-%m-%dT%H:%MZ")
    r = requests.get(f"https://api.carbonintensity.org.uk/regional/intensity/{start}/fw48h/postcode/{outcode}", timeout=30)
    r.raise_for_status()
    d = r.json()["data"]
    if isinstance(d, list):
        d = d[0]
    rows = []
    for p in d["data"]:
        row = {"time": p["from"], "carbon": p["intensity"]["forecast"], "index": p["intensity"]["index"]}
        for g in p.get("generationmix", []):
            row[g["fuel"]] = g["perc"]
        rows.append(row)
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return d["regionid"], d["shortname"], df


@st.cache_data(ttl=3600, show_spinner=False)
def agile_product():
    r = requests.get("https://api.octopus.energy/v1/products/",
                     params={"brand": "OCTOPUS_ENERGY", "is_variable": "true", "page_size": 100}, timeout=30)
    agile = [p for p in r.json()["results"] if p["code"].startswith("AGILE") and p.get("direction") == "IMPORT"]
    return sorted(agile, key=lambda p: p["available_from"], reverse=True)[0]["code"]


@st.cache_data(ttl=1800, show_spinner=False)
def agile_prices(letter):
    product = agile_product()
    url = (f"https://api.octopus.energy/v1/products/{product}/electricity-tariffs/"
           f"E-1R-{product}-{letter}/standard-unit-rates/")
    r = requests.get(url, params={"period_from": now_utc().strftime("%Y-%m-%dT%H:%MZ"), "page_size": 200}, timeout=30)
    df = pd.DataFrame(r.json()["results"])
    if df.empty:
        return pd.DataFrame(columns=["time", "price"])
    df["time"] = pd.to_datetime(df["valid_from"], utc=True)
    return df[["time", "value_inc_vat"]].rename(columns={"value_inc_vat": "price"})


def norm(s):
    return (s - s.min()) / (s.max() - s.min()) if s.max() != s.min() else s * 0


def label(t):
    return t.tz_convert(UK).strftime("%a %H:%M")


# ---------------- UI
st.title("⚡ UK Grid Live")
st.caption("When is electricity cleanest and cheapest where you live? Live data from National Grid ESO and Octopus Energy Agile.")

c1, c2, c3 = st.columns([1.2, 1.5, 1.5])
postcode = c1.text_input("Your postcode", "WA1 1AA")
appliance = c2.selectbox("What do you want to run?", list(APPLIANCES))
priority = c3.slider("Priority", 0, 100, 50, help="0 = cheapest, 100 = greenest")
c3.caption("💷 Cheapest ←→ Greenest 🌱")

try:
    region_id, region_name, carbon = carbon_forecast(outward(postcode))
except Exception:
    st.error("Couldn't find that postcode. Try the first part only, e.g. M1, WA1, EH1.")
    st.stop()

letter = REGION_TO_LETTER.get(region_id)
prices = agile_prices(letter) if letter else pd.DataFrame(columns=["time", "price"])
df = carbon.merge(prices, on="time", how="left")
df["local"] = df["time"].dt.tz_convert(UK).dt.tz_localize(None)

# ---------------- Right now
now = df.iloc[0]
st.subheader(f"Right now in {region_name}")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Carbon intensity", f"{now['carbon']} g/kWh", now["index"].title(), delta_color="off")
m2.metric("Agile price", f"{now['price']:.1f}p/kWh" if pd.notna(now["price"]) else "n/a")
m3.metric("Wind share", f"{now.get('wind', 0):.0f}%")
m4.metric("Gas share", f"{now.get('gas', 0):.0f}%")

# ---------------- Best time planner
n = APPLIANCES[appliance]
plan = df.dropna(subset=["price"]).reset_index(drop=True) if df["price"].notna().sum() >= n else df.copy()
has_price = plan["price"].notna().all() and len(plan) >= n
w = priority / 100
plan["score"] = w * norm(plan["carbon"]) + ((1 - w) * norm(plan["price"]) if has_price else 0)
plan["window_score"] = plan["score"].rolling(n).mean().shift(-(n - 1))
best_i = plan["window_score"].idxmin()
best = plan.iloc[best_i:best_i + n]
nowwin = plan.iloc[0:n]

st.subheader(f"Best time for: {appliance}")
b1, b2, b3, b4 = st.columns(4)
b1.metric("Start at", label(best["time"].iloc[0]))
b2.metric("Avg carbon", f"{best['carbon'].mean():.0f} g/kWh",
          f"{best['carbon'].mean() / max(nowwin['carbon'].mean(), 1) - 1:+.0%} vs now", delta_color="inverse")
if has_price:
    b3.metric("Avg price", f"{best['price'].mean():.1f}p/kWh",
              f"{best['price'].mean() - nowwin['price'].mean():+.1f}p vs now", delta_color="inverse")
b4.metric("Window", f"{label(best['time'].iloc[0])} – {(best['time'].iloc[-1] + timedelta(minutes=30)).tz_convert(UK).strftime('%H:%M')}")
if not has_price:
    st.info("Agile prices for this period aren't published yet (Octopus publishes around 4pm for the next day), so this plan uses carbon only.")

# ---------------- Chart
band = pd.DataFrame({"start": [best["local"].iloc[0]], "end": [best["local"].iloc[-1] + timedelta(minutes=30)]})
x = alt.X("local:T", title=None, axis=alt.Axis(format="%a %H:%M"))
highlight = alt.Chart(band).mark_rect(color="#facc15", opacity=0.18).encode(x="start:T", x2="end:T")
carbon_line = alt.Chart(df).mark_line(color="#22c55e", strokeWidth=3).encode(
    x=x, y=alt.Y("carbon:Q", title="Carbon (gCO2/kWh)"),
    tooltip=[alt.Tooltip("local:T", format="%a %H:%M", title="Time"), "carbon", "index"])
layers = [highlight, carbon_line]
if df["price"].notna().any():
    price_bars = alt.Chart(df.dropna(subset=["price"])).mark_bar(color="#60a5fa", opacity=0.45).encode(
        x=x, y=alt.Y("price:Q", title="Price (p/kWh)"),
        tooltip=[alt.Tooltip("local:T", format="%a %H:%M", title="Time"), alt.Tooltip("price:Q", format=".2f")])
    layers = [highlight, price_bars, carbon_line]
st.altair_chart(alt.layer(*layers).resolve_scale(y="independent").properties(height=380), use_container_width=True)
st.caption("🟩 carbon forecast (48h)  🟦 Agile price  🟨 best window")

# ---------------- Insights from 90 days
with st.expander("📊 What 90 days of data showed (Jul–Oct 2026)"):
    st.markdown("""
- **Location matters most:** North Scotland averaged **0 g/kWh**, South Wales **270 g/kWh**.
- **Midday is the sweet spot:** shifting use from 6pm to 1pm cut price by **64%** and carbon by **50%**.
- **4–7pm peak** prices averaged **76% higher** than the rest of the day.
- **Windy half-hours** had **~6x lower carbon** than calm ones.
- **Weekends** were **20% cheaper** and **13% cleaner**.
- **2,590** regional half-hours had **negative prices** (down to -5.5p).
""")
    try:
        st.image("docs/images/forecast_vs_actual.png",
                 caption="My 24h-ahead model (with offshore wind forecasts) beat a naive baseline by 42%")
    except Exception:
        pass

st.divider()
st.caption("Built by Shaheer Ahmad · Python · Azure Blob · Azure SQL · GitHub Actions · scikit-learn · Streamlit · "
           "[GitHub](https://github.com/chshery/uk-grid-live) · Data: Carbon Intensity API (NESO), Octopus Energy API, Open-Meteo")