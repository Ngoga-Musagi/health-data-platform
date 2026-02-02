SELECT
    country_code,
    country_name,
    year,
    AVG(life_expectancy) AS avg_life_expectancy
FROM {{ ref('stg_health_life_expectancy') }}
GROUP BY country_code, country_name, year
