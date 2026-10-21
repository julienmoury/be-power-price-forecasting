-- Error of each model by delivery hour (Brussels time), since the first live day.
SELECT hour,
       avg(error) FILTER (model = 'naive') AS naive,
       avg(error) FILTER (model = 'lear') AS lear,
       avg(error) FILTER (model = 'dnn') AS dnn
FROM errors
WHERE day IN (SELECT day FROM errors GROUP BY day HAVING count(DISTINCT model) = 3)
GROUP BY hour
ORDER BY hour;
