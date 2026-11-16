SELECT e.establishment_id, e.source_id, e.name, e.average_rating
FROM tiago_lab.establishment e
WHERE e.average_rating >= 4
  AND EXISTS (SELECT 1 FROM tiago_lab.establishment_label l
              WHERE l.establishment_id = e.establishment_id AND l.label = 'Sushi')
ORDER BY e.average_rating DESC, e.establishment_id;

SELECT e.establishment_id, e.source_id, e.name,
       count(v.visit_id) AS visit_events,
       coalesce(sum(v.party_size), 0) AS simulated_attendances
FROM tiago_lab.establishment e
LEFT JOIN tiago_lab.visit v ON v.establishment_id = e.establishment_id
    AND v.visited_at >= TIMESTAMPTZ '2026-09-01 00:00:00 Europe/Lisbon'
    AND v.visited_at < TIMESTAMPTZ '2026-10-01 00:00:00 Europe/Lisbon'
GROUP BY e.establishment_id, e.source_id, e.name
ORDER BY simulated_attendances DESC, e.establishment_id;

SELECT e.source_id, e.name,
       count(DISTINCT v.person_id) AS distinct_registered_people,
       sum(v.party_size) AS simulated_attendances
FROM tiago_lab.establishment e
JOIN tiago_lab.visit v USING (establishment_id)
WHERE e.average_rating >= 4
  AND EXISTS (SELECT 1 FROM tiago_lab.establishment_label l
              WHERE l.establishment_id = e.establishment_id AND l.label = 'Sushi')
  AND v.visited_at >= TIMESTAMPTZ '2026-09-01 00:00:00 Europe/Lisbon'
  AND v.visited_at < TIMESTAMPTZ '2026-10-01 00:00:00 Europe/Lisbon'
GROUP BY e.source_id, e.name
HAVING count(DISTINCT v.person_id) >= 2
ORDER BY e.source_id;
