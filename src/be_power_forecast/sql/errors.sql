-- Hourly absolute error of each model, from the first live day.
-- Tables: forecasts(model, day, hour, price) and realised(day, hour, price).
-- The naive forecast copies the same day of last week on Mondays, Saturdays and
-- Sundays, the previous day otherwise (dayofweek: 0 = Sunday, 6 = Saturday).
CREATE OR REPLACE VIEW errors AS
WITH naive AS (
    SELECT 'naive' AS model, d.day, r.hour, r.price
    FROM (SELECT DISTINCT day FROM realised) AS d
    JOIN realised AS r
      ON r.day = d.day - CASE WHEN dayofweek(d.day) IN (0, 1, 6) THEN 7 ELSE 1 END
)
SELECT f.model, f.day, f.hour, abs(f.price - r.price) AS error
FROM (SELECT * FROM forecasts UNION ALL SELECT * FROM naive) AS f
JOIN realised AS r USING (day, hour)
WHERE f.day >= DATE '{start}';
