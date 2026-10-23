# Key Findings (90 days, Jul–Oct 2026, 14 GB regions)

1. **Location matters most.** North Scotland averaged 0 gCO2/kWh, while South Wales averaged 270 and South West England 257, because Scotland runs on wind and hydro and the south relies on gas.
2. **Midday is the sweet spot.** 12–2pm is both the cleanest time (67 g) and among the cheapest (18p). Moving usage from 6pm to 1pm cuts price by 64% (49.8p to 17.9p) and carbon by 50%.
3. **The 4–7pm peak is expensive.** Agile prices average 44.8p at peak vs 25.5p off-peak, 76% higher.
4. **Wind drives everything.** In windy half-hours (40%+ wind) carbon averaged 36 g vs 206 g when calm, nearly 6 times lower, and prices were 17% lower.
5. **Weekends are cleaner and cheaper.** They are 13% lower in carbon and 20% cheaper than weekdays.
6. **Cheap is not always clean.** Price and carbon correlate only weakly (r = 0.25), so a carbon signal adds information beyond price alone.
7. **You can get paid to use power.** 2,590 regional half-hours had negative prices, down to -5.5p/kWh.
8. **National Grid's forecast is strong:** a mean absolute error of 12.5 g, which is the benchmark for my model.

## Data quality
- 0 duplicates, 0 missing half-hours, every generation mix sums to 100%, and no out-of-range values.
- There are 14 missing prices, all at the first half-hour (25 Jul 20:30 UTC). The carbon API returns one period before the requested start, so this is a boundary effect.
- 1 missing national actual: the latest period, not yet measured.
- 2,590 negative prices are kept on purpose because they are real Agile behaviour.