-- Q1 (simples): estabelecimentos de sushi com avaliacao >= 4.
-- Esperado: Wood Sushi in a Box (4.5) e Miss Jappa (4.0).
SELECT e.establishment_id, e.name, e.average_rating
FROM tiago_lab.establishment e
JOIN tiago_lab.establishment_label l USING (establishment_id)
WHERE l.label = 'Sushi' AND e.average_rating >= 4
ORDER BY e.average_rating DESC, e.establishment_id;

-- Q2 (intermedia): visitas e presencas simuladas por estabelecimento em setembro.
-- Esperado: 8 estabelecimentos, incluindo 3 com zero visitas; total de 15 presencas.
-- Os limites sao o inicio e fim do mes em Lisboa (UTC+1 nestas datas).
-- COUNT(v.visit_id), e nao COUNT(*), preserva corretamente os zeros.
SELECT e.establishment_id, e.name,
       count(v.visit_id) AS visit_events,
       coalesce(sum(v.party_size), 0) AS simulated_attendances
FROM tiago_lab.establishment e
LEFT JOIN tiago_lab.visit v ON v.establishment_id = e.establishment_id
    AND v.visited_at >= TIMESTAMPTZ '2026-09-01 00:00:00+01'
    AND v.visited_at <  TIMESTAMPTZ '2026-10-01 00:00:00+01'
GROUP BY e.establishment_id, e.name
ORDER BY simulated_attendances DESC, e.establishment_id;

-- Q3 (complexa neste exercicio): locais de sushi >=4, visitados em setembro
-- por pelo menos 2 pessoas identificadas diferentes; indicar presencas.
-- Esperado: Miss Jappa, 3 pessoas responsaveis distintas, 7 presencas.
-- EXISTS evita multiplicar as visitas pelas varias etiquetas do local.
SELECT e.establishment_id, e.name,
       count(DISTINCT v.person_id) AS distinct_registered_people,
       sum(v.party_size) AS simulated_attendances
FROM tiago_lab.establishment e
JOIN tiago_lab.visit v USING (establishment_id)
WHERE e.average_rating >= 4
  AND EXISTS (SELECT 1 FROM tiago_lab.establishment_label l
              WHERE l.establishment_id = e.establishment_id AND l.label = 'Sushi')
  AND v.visited_at >= TIMESTAMPTZ '2026-09-01 00:00:00+01'
  AND v.visited_at <  TIMESTAMPTZ '2026-10-01 00:00:00+01'
GROUP BY e.establishment_id, e.name
HAVING count(DISTINCT v.person_id) >= 2
ORDER BY e.establishment_id;
