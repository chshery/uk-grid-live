-- name: Q1 duplicate keys (expect 0)
SELECT COUNT(*) AS duplicates FROM (
  SELECT datetime_key, region_id FROM fact_grid
  GROUP BY datetime_key, region_id HAVING COUNT(*) > 1) d;

-- name: Q2 missing half-hours (expect 0)
SELECT DATEDIFF(MINUTE, MIN(utc_datetime), MAX(utc_datetime)) / 30 + 1 AS expected_periods,
       COUNT(*) AS actual_periods,
       DATEDIFF(MINUTE, MIN(utc_datetime), MAX(utc_datetime)) / 30 + 1 - COUNT(*) AS missing
FROM dim_datetime;

-- name: Q3 generation mix not summing to 100% (+/-1)
SELECT COUNT(*) AS bad_mix_rows FROM fact_grid
WHERE ABS(ISNULL(mix_gas,0)+ISNULL(mix_coal,0)+ISNULL(mix_nuclear,0)+ISNULL(mix_wind,0)+ISNULL(mix_solar,0)
         +ISNULL(mix_hydro,0)+ISNULL(mix_biomass,0)+ISNULL(mix_imports,0)+ISNULL(mix_other,0) - 100) > 1;

-- name: Q4 carbon values out of range (<0 or >1000)
SELECT COUNT(*) AS out_of_range FROM fact_grid
WHERE forecast_gco2 < 0 OR forecast_gco2 > 1000;

-- name: Q5 missing prices - which periods?
SELECT d.utc_datetime, COUNT(*) AS regions_missing
FROM fact_grid f JOIN dim_datetime d ON d.datetime_key = f.datetime_key
WHERE f.region_id <= 14 AND f.price_inc_vat_p IS NULL
GROUP BY d.utc_datetime;

-- name: Q6 negative price periods (real Agile feature, not an error)
SELECT COUNT(*) AS negative_price_rows, MIN(price_inc_vat_p) AS lowest_price_p
FROM fact_grid WHERE price_inc_vat_p < 0;