-- As duas consultas devem devolver zero linhas.
-- Regras entre tabelas que esta primeira versao verifica na validacao,
-- sem afirmar que um CHECK de uma linha protege uma regra entre tabelas.
SELECT v.visit_id, r.reservation_id, r.status
FROM tiago_lab.visit v JOIN tiago_lab.reservation r USING (reservation_id)
WHERE r.status <> 'fulfilled'
   OR v.visited_at < r.created_at
   OR v.party_size <> r.party_size;

SELECT r.reservation_id
FROM tiago_lab.reservation r
LEFT JOIN tiago_lab.visit v USING (reservation_id)
WHERE r.status = 'fulfilled' AND v.visit_id IS NULL;
