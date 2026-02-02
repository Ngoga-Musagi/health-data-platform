SELECT
    country_name,
    country_code,
    year,
    sex,
    life_expectancy,
    ingested_at
FROM {{ source('raw_warehouse', 'health_life_expectancy') }}
WHERE life_expectancy IS NOT NULL
