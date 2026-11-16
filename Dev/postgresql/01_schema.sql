-- Iteracao 1: fonte local B1. Executar numa base de dados de trabalho nova.
-- O esquema e os dados do ZIP da proposta nao sao utilizados.
BEGIN;
CREATE SCHEMA tiago_lab;

-- Uma linha por estabelecimento da amostra real (catalogo de maio de 2021).
CREATE TABLE tiago_lab.establishment (
    establishment_id integer PRIMARY KEY,
    source_id text NOT NULL UNIQUE,
    name text NOT NULL CHECK (btrim(name) <> ''),
    address text,
    latitude numeric CHECK (latitude BETWEEN -90 AND 90),
    longitude numeric CHECK (longitude BETWEEN -180 AND 180),
    average_rating numeric(2,1) CHECK (average_rating BETWEEN 0 AND 5),
    review_count integer CHECK (review_count >= 0),
    CHECK ((latitude IS NULL) = (longitude IS NULL))
);

-- Uma linha por etiqueta original de um estabelecimento.
-- A coluna cuisines da origem mistura culinarias (Sushi) e tipos (Cafe, Bar, Pub).
CREATE TABLE tiago_lab.establishment_label (
    establishment_id integer REFERENCES tiago_lab.establishment,
    label text CHECK (btrim(label) <> ''),
    PRIMARY KEY (establishment_id, label)
);

-- Uma linha por pessoa ficticia identificada pelo par natural (display_name, contact_phone).
CREATE TABLE tiago_lab.person (
    person_id integer PRIMARY KEY,
    display_name text NOT NULL CHECK (btrim(display_name) <> ''),
    contact_phone text NOT NULL CHECK (btrim(contact_phone) <> ''),
    is_synthetic boolean NOT NULL DEFAULT true CHECK (is_synthetic),
    UNIQUE (display_name, contact_phone)
);

-- Uma linha por reserva; uma pessoa pode reservar varias vezes o mesmo local em instantes distintos.
CREATE TABLE tiago_lab.reservation (
    reservation_id integer PRIMARY KEY,
    person_id integer NOT NULL REFERENCES tiago_lab.person,
    establishment_id integer NOT NULL REFERENCES tiago_lab.establishment,
    created_at timestamptz NOT NULL,
    scheduled_at timestamptz NOT NULL,
    party_size integer NOT NULL CHECK (party_size > 0),
    status text NOT NULL CHECK (status IN ('confirmed','fulfilled','cancelled','no_show')),
    is_synthetic boolean NOT NULL DEFAULT true CHECK (is_synthetic),
    CHECK (created_at <= scheduled_at),
    UNIQUE (person_id, establishment_id, scheduled_at),
    UNIQUE (reservation_id, person_id, establishment_id)
);

-- Uma linha por visita realizada no cenario simulado, com ou sem reserva.
-- A pessoa identificada e o responsavel do grupo; os acompanhantes nao sao identificados.
CREATE TABLE tiago_lab.visit (
    visit_id integer PRIMARY KEY,
    person_id integer NOT NULL REFERENCES tiago_lab.person,
    establishment_id integer REFERENCES tiago_lab.establishment,
    cultural_place_id text,
    reservation_id integer UNIQUE,
    visited_at timestamptz NOT NULL,
    party_size integer NOT NULL CHECK (party_size > 0),
    is_synthetic boolean NOT NULL DEFAULT true CHECK (is_synthetic),
    CHECK (num_nonnulls(establishment_id, cultural_place_id) = 1),
    CHECK (cultural_place_id IS NULL OR btrim(cultural_place_id) <> ''),
    CHECK (reservation_id IS NULL OR establishment_id IS NOT NULL),
    UNIQUE (person_id, visited_at),
    FOREIGN KEY (reservation_id, person_id, establishment_id)
        REFERENCES tiago_lab.reservation (reservation_id, person_id, establishment_id)
);
-- cultural_place_id e uma referencia EXTERNA ao XML, validada pelo adaptador.
-- Nao existe uma FK PostgreSQL que verifique diretamente uma base BaseX.
-- Coerencia entre estado da reserva e visita: verificacao em 04_quality.sql.
COMMIT;
