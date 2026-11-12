-- Error of each model per day (EUR/MWh).
SELECT day,
       avg(error) FILTER (model = 'naive') AS naive,
       avg(error) FILTER (model = 'lear') AS lear,
       avg(error) FILTER (model = 'dnn') AS dnn,
       avg(error) FILTER (model = 'lgbm') AS lgbm
FROM errors
GROUP BY day
ORDER BY day;
