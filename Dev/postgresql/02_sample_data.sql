-- Dados reais do catalogo 2021; pessoas, reservas e visitas SINTETICAS.
BEGIN;
INSERT INTO tiago_lab.establishment (establishment_id,source_id,name,address,latitude,longitude,average_rating,review_count) VALUES
(1, 'g189158-d10002838', 'Miss Jappa', 'Praca Principe Real 5 A, Lisbon 1250-184 Portugal', 38.715668, -9.148492, 4.0, 135),
(2, 'g189158-d10003138', 'Gaijin Sushi Bar', 'Rua do Polo Norte 17, Lisbon 1990-263 Portugal', 38.77155, -9.096183, 3.0, 67),
(3, 'g189158-d10005260', 'Wood Sushi in a Box', 'Avenida Dom Joao II 39A, Lisbon 1990-083 Portugal', 38.77057, -9.097896, 4.5, 47),
(4, 'g189158-d10005571', 'Paul (Rua Augusta)', 'Rua Augusta Nº 142, Lisbon 1100-054 Portugal', 38.7107, -9.137744, 4.0, 332),
(5, 'g189158-d10044675', 'Cervejeira Lusitana', 'Avenida Lusiada Centro Comercial Colombo, Lisbon 1500-392 Portugal', 38.75438, -9.187344, 3.0, 26),
(6, 'g189158-d10130339', 'Weekend Cocktail Bar', 'Rua Augusto Gil 19B, Lisbon 1000-063 Portugal', 38.74372, -9.14073, 4.5, 7),
(7, 'g189158-d10003850', 'Terra Vermelha', 'Avenida Tomas Ribeiro n 64B, Lisbon 2795-184 Portugal', 38.71535, -9.24442, NULL, 0),
(8, 'g189158-d10087956', 'O Sinal', 'Rua Camilo Castelo Branco 28 Marques de Pombal, Lisbon 1150-084 Portugal', 38.72548, -9.148486, 4.0, 20);
INSERT INTO tiago_lab.establishment_label (establishment_id,label) VALUES
(1, 'Asian'),
(1, 'Japanese'),
(1, 'Sushi'),
(2, 'Asian'),
(2, 'Japanese'),
(2, 'Sushi'),
(3, 'Asian'),
(3, 'Japanese'),
(3, 'Sushi'),
(4, 'Cafe'),
(4, 'European'),
(4, 'French'),
(5, 'Bar'),
(5, 'European'),
(5, 'Portuguese'),
(5, 'Pub'),
(6, 'Bar'),
(6, 'European'),
(6, 'Portuguese'),
(6, 'Pub'),
(8, 'Bar'),
(8, 'European'),
(8, 'Portuguese'),
(8, 'Pub');
INSERT INTO tiago_lab.person (person_id,display_name,contact_phone) VALUES
(1, 'Ana Exemplo', '+351910000001'),
(2, 'Bruno Exemplo', '+351910000002'),
(3, 'Ana Exemplo', '+351910000003'),
(4, 'Carla Exemplo', '+351910000002'),
(5, 'Diogo Exemplo', '+351910000005'),
(6, 'Eva Exemplo', '+351910000006');
INSERT INTO tiago_lab.reservation (reservation_id,person_id,establishment_id,created_at,scheduled_at,party_size,status) VALUES
(101, 1, 1, '2026-09-09 10:00+01', '2026-09-10 20:00+01', 2, 'fulfilled'),
(102, 2, 1, '2026-09-10 10:00+01', '2026-09-12 20:00+01', 4, 'cancelled'),
(103, 1, 3, '2026-09-13 10:00+01', '2026-09-15 20:00+01', 3, 'fulfilled'),
(104, 3, 3, '2026-09-15 10:00+01', '2026-09-17 20:00+01', 2, 'no_show'),
(105, 4, 4, '2026-09-16 10:00+01', '2026-09-18 12:00+01', 1, 'fulfilled'),
(106, 5, 6, '2026-10-20 10:00+01', '2026-10-25 20:00+00', 4, 'confirmed'),
(107, 2, 8, '2026-09-20 10:00+01', '2026-09-22 20:00+01', 2, 'fulfilled');
INSERT INTO tiago_lab.visit (visit_id,person_id,establishment_id,cultural_place_id,reservation_id,visited_at,party_size) VALUES
(1001, 1, 1, NULL, 101, '2026-09-10 20:00+01', 2),
(1002, 1, 3, NULL, 103, '2026-09-15 20:00+01', 3),
(1003, 4, 4, NULL, 105, '2026-09-18 12:00+01', 1),
(1004, 2, 8, NULL, 107, '2026-09-22 20:00+01', 2),
(1005, 3, 1, NULL, NULL, '2026-09-20 20:00+01', 1),
(1006, 2, 1, NULL, NULL, '2026-09-24 20:00+01', 4),
(1007, 3, 5, NULL, NULL, '2026-09-28 20:00+01', 2),
(1008, 1, NULL, 'museum:0454d65e-4c82-40da-8ab4-37e865aa86a6', NULL, '2026-09-11 14:00+01', 2),
(1009, 2, NULL, 'museum:0454d65e-4c82-40da-8ab4-37e865aa86a6', NULL, '2026-09-25 14:00+01', 4),
(1010, 3, NULL, 'monument:005ffb1e-a50b-4893-891a-dc44d0693890', NULL, '2026-09-29 14:00+01', 2),
(1011, 5, 6, NULL, NULL, '2026-10-10 20:00+01', 2),
(1012, 1, 1, NULL, NULL, '2026-10-01 00:00+01', 1);
COMMIT;
