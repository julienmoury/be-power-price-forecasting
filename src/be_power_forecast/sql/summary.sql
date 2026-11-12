-- Mean error of each model since the first live day and over the last 7 days,
-- on the days where every model has a forecast.
WITH complete AS (
    SELECT day FROM errors GROUP BY day
    HAVING count(DISTINCT model) = (SELECT count(DISTINCT model) FROM errors)
)
SELECT model,
       avg(error) AS since_start,
       avg(error) FILTER (day > (SELECT max(day) FROM complete) - 7) AS last_7_days,
       count(DISTINCT day) AS days
FROM errors
WHERE day IN (SELECT day FROM complete)
GROUP BY model
ORDER BY since_start;
