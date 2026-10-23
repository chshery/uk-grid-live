IF OBJECT_ID('fact_grid','U') IS NOT NULL DROP TABLE fact_grid;
IF OBJECT_ID('fact_national','U') IS NOT NULL DROP TABLE fact_national;
IF OBJECT_ID('dim_region','U') IS NOT NULL DROP TABLE dim_region;
IF OBJECT_ID('dim_datetime','U') IS NOT NULL DROP TABLE dim_datetime;
GO
CREATE TABLE dim_region (
    region_id      INT          PRIMARY KEY,
    region_name    VARCHAR(50)  NOT NULL,
    octopus_code   CHAR(1)      NULL,
    region_level   VARCHAR(10)  NOT NULL   -- 'region' or 'nation'
);
GO
CREATE TABLE dim_datetime (
    datetime_key       BIGINT      PRIMARY KEY,   -- YYYYMMDDHHMM (UTC)
    utc_datetime       DATETIME2   NOT NULL,
    local_datetime     DATETIME2   NOT NULL,      -- Europe/London
    local_date         DATE        NOT NULL,
    local_hour         TINYINT     NOT NULL,
    settlement_period  TINYINT     NOT NULL,      -- 1-48
    day_name           VARCHAR(10) NOT NULL,
    is_weekend         BIT         NOT NULL,
    month_name         VARCHAR(10) NOT NULL
);
GO
CREATE TABLE fact_grid (
    datetime_key     BIGINT      NOT NULL REFERENCES dim_datetime(datetime_key),
    region_id        INT         NOT NULL REFERENCES dim_region(region_id),
    forecast_gco2    INT         NULL,
    intensity_index  VARCHAR(12) NULL,
    mix_gas          FLOAT NULL, mix_coal    FLOAT NULL, mix_nuclear FLOAT NULL,
    mix_wind         FLOAT NULL, mix_solar   FLOAT NULL, mix_hydro   FLOAT NULL,
    mix_biomass      FLOAT NULL, mix_imports FLOAT NULL, mix_other   FLOAT NULL,
    price_inc_vat_p  FLOAT NULL,
    PRIMARY KEY (datetime_key, region_id)
);
GO
CREATE TABLE fact_national (
    datetime_key      BIGINT PRIMARY KEY REFERENCES dim_datetime(datetime_key),
    ng_forecast_gco2  INT NULL,
    actual_gco2       INT NULL,
    intensity_index   VARCHAR(12) NULL
);
GO