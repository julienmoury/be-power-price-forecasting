-- Error of each model by delivery hour (Brussels time), since the first live day.
SELECT hour,
       avg(error) FILTER (model = 'naive') AS naive,
       avg(error) FILTER (model = 'lear') AS lear,
       avg(error) FILTER (model = 'dnn') AS dnn,
       avg(error) FILTER (model = 'lgbm') AS lgbm
FROM errors
WHERE day IN (
    SELECT day FROM errors GROUP BY day
    HAVING count(DISTINCT model) = (SELECT count(DISTINCT model) FROM errors)
)
GROUP BY hour
ORDER BY hour;
