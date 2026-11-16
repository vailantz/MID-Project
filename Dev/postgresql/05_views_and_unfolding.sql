-- Interfaces locais e uma vista definida por GAV (Global-as-View).
CREATE VIEW tiago_lab.food_visit AS
SELECT DISTINCT person_id, establishment_id
FROM tiago_lab.visit
WHERE establishment_id IS NOT NULL;

CREATE VIEW tiago_lab.cultural_visit AS
SELECT DISTINCT person_id, cultural_place_id
FROM tiago_lab.visit
WHERE cultural_place_id IS NOT NULL;

-- Vista local que deixa explicito o significado de "visitou sushi".
CREATE VIEW tiago_lab.sushi_visitor AS
SELECT DISTINCT v.person_id, v.establishment_id
FROM tiago_lab.food_visit v
JOIN tiago_lab.establishment_label l USING (establishment_id)
WHERE l.label = 'Sushi';

-- Consulta sobre a vista.
SELECT DISTINCT person_id FROM tiago_lab.sushi_visitor ORDER BY person_id;

-- A mesma consulta depois de expandir as definicoes (unfolding).
SELECT DISTINCT v.person_id
FROM tiago_lab.visit v
JOIN tiago_lab.establishment_label l USING (establishment_id)
WHERE v.establishment_id IS NOT NULL AND l.label = 'Sushi'
ORDER BY v.person_id;

-- Ambas devem devolver 1, 2, 3 neste exemplo. A justificacao geral esta no guia.
