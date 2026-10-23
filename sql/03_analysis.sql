-- name: A1 cleanest vs dirtiest regions (avg gCO2/kWh)
SELECT r.region_name,
       ROUND(AVG(CAST(f.forecast_gco2 AS FLOAT)),1) AS avg_gco2,
       ROUND(AVG(f.price_inc_vat_p),2) AS avg_price_p
FROM fact_grid f JOIN dim_region r ON r.region_id = f.region_id
WHERE r.region_level = 'region'
GROUP BY r.region_name ORDER BY avg_gco2;

-- name: A2 hour of day - carbon and price (all 14 regions, UK time)
SELECT d.local_hour,
       ROUND(AVG(CAST(f.forecast_gco2 AS FLOAT)),1) AS avg_gco2,
       ROUND(AVG(f.price_inc_vat_p),2) AS avg_price_p
FROM fact_grid f JOIN dim_datetime d ON d.datetime_key = f.datetime_key
WHERE f.region_id <= 14
GROUP BY d.local_hour ORDER BY d.local_hour;

-- name: A3 correlation between price and carbon
SELECT ROUND(
  (AVG(CAST(forecast_gco2 AS FLOAT)*price_inc_vat_p) - AVG(CAST(forecast_gco2 AS FLOAT))*AVG(price_inc_vat_p))
  / (STDEVP(CAST(forecast_gco2 AS FLOAT)) * STDEVP(price_inc_vat_p)), 3) AS correlation
FROM fact_grid WHERE region_id <= 14 AND price_inc_vat_p IS NOT NULL;

-- name: A4 peak 4-7pm vs rest of day
SELECT CASE WHEN d.local_hour BETWEEN 16 AND 18 THEN 'Peak 4-7pm' ELSE 'Off-peak' END AS period,
       ROUND(AVG(f.price_inc_vat_p),2) AS avg_price_p,
       ROUND(AVG(CAST(f.forecast_gco2 AS FLOAT)),1) AS avg_gco2
FROM fact_grid f JOIN dim_datetime d ON d.datetime_key = f.datetime_key
WHERE f.region_id <= 14
GROUP BY CASE WHEN d.local_hour BETWEEN 16 AND 18 THEN 'Peak 4-7pm' ELSE 'Off-peak' END;

-- name: A5 wind effect on carbon and price
SELECT CASE WHEN mix_wind >= 40 THEN 'Windy (40%+)'
            WHEN mix_wind < 15 THEN 'Calm (<15%)' ELSE 'Medium' END AS wind_level,
       COUNT(*) AS half_hours,
       ROUND(AVG(CAST(forecast_gco2 AS FLOAT)),1) AS avg_gco2,
       ROUND(AVG(price_inc_vat_p),2) AS avg_price_p
FROM fact_grid WHERE region_id <= 14
GROUP BY CASE WHEN mix_wind >= 40 THEN 'Windy (40%+)'
              WHEN mix_wind < 15 THEN 'Calm (<15%)' ELSE 'Medium' END
ORDER BY avg_gco2;

-- name: A6 weekday vs weekend
SELECT CASE WHEN d.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END AS day_type,
       ROUND(AVG(CAST(f.forecast_gco2 AS FLOAT)),1) AS avg_gco2,
       ROUND(AVG(f.price_inc_vat_p),2) AS avg_price_p
FROM fact_grid f JOIN dim_datetime d ON d.datetime_key = f.datetime_key
WHERE f.region_id <= 14
GROUP BY d.is_weekend;

-- name: A7 National Grid forecast accuracy (baseline to beat)
SELECT COUNT(*) AS periods,
       ROUND(AVG(ABS(CAST(ng_forecast_gco2 - actual_gco2 AS FLOAT))),2) AS mae_gco2,
       ROUND(AVG(CAST(ng_forecast_gco2 - actual_gco2 AS FLOAT)),2) AS bias_gco2
FROM fact_national WHERE actual_gco2 IS NOT NULL;