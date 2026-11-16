"""Valida o cenario ficticio e gera SQL separado do catalogo real."""
from collections import Counter
from datetime import datetime
import csv
import json
import xml.etree.ElementTree as ET

from prepare_full_catalogue import ROOT, SOURCE, OUTPUT, prepare, sha256, sql_text

FIXTURE = ROOT/'data/synthetic_activity.json'
ACTIVITY_SQL = OUTPUT/'synthetic_activity.sql'
ACTIVITY_MANIFEST = OUTPUT/'synthetic_activity_manifest.json'
XML_PATH = ROOT/'data/cultural_catalogue.xml'
COLUMNS = {
    'people': ['person_id', 'display_name', 'contact_phone'],
    'reservations': ['reservation_id', 'person_id', 'establishment_source_id',
                     'created_at', 'scheduled_at', 'party_size', 'status'],
    'visits': ['visit_id', 'person_id', 'establishment_source_id', 'cultural_place_id',
               'reservation_id', 'visited_at', 'party_size'],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def instant(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.utcoffset() is not None, 'Instante sem fuso explicito')
    return parsed


def positive(value):
    return type(value) is int and 0 < value <= 2147483647


def validate(scenario, source_ids, cultural_ids):
    require(scenario['is_synthetic'] is True, 'Cenario deve ser explicitamente sintetico')
    require(scenario['time_zone'] == 'Europe/Lisbon', 'Fuso inesperado')
    require(scenario['columns'] == COLUMNS, 'Colunas do cenario inesperadas')
    cutoff = instant(scenario['scenario_as_of'])
    records = {}
    for section, columns in COLUMNS.items():
        records[section] = [dict(zip(columns, row, strict=True)) for row in scenario[section]]
        keys = [row[columns[0]] for row in records[section]]
        require(all(positive(key) for key in keys), 'IDs invalidos em ' + section)
        require(len(keys) == len(set(keys)), 'IDs repetidos em ' + section)
    people = {row['person_id']: row for row in records['people']}
    reservations = {row['reservation_id']: row for row in records['reservations']}
    require(all(isinstance(row['display_name'], str) and row['display_name'].strip()
                and isinstance(row['contact_phone'], str) and row['contact_phone'].strip()
                for row in people.values()), 'Nome ou telefone de pessoa vazio')
    person_natural_keys = [(row['display_name'], row['contact_phone']) for row in people.values()]
    require(len(person_natural_keys) == len(set(person_natural_keys)),
            'Chave natural composta (display_name, contact_phone) repetida em people')
    reservation_natural_keys = []
    for row in reservations.values():
        require(positive(row['person_id']) and row['person_id'] in people, 'Pessoa da reserva inexistente')
        require(row['establishment_source_id'] in source_ids, 'Estabelecimento da reserva inexistente')
        require(positive(row['party_size']), 'Grupo da reserva invalido')
        require(row['status'] in ('confirmed', 'fulfilled', 'cancelled', 'no_show'), 'Estado invalido')
        created, scheduled = instant(row['created_at']), instant(row['scheduled_at'])
        require(created <= scheduled and created <= cutoff, 'Datas da reserva incoerentes')
        if row['status'] in ('fulfilled', 'no_show'):
            require(scheduled <= cutoff, 'Reserva cumprida/falta futura')
        if row['status'] == 'confirmed':
            require(scheduled > cutoff, 'Confirmacoes deste cenario devem ser futuras na data de referencia')
        reservation_natural_keys.append((row['person_id'], row['establishment_source_id'], scheduled))
    require(len(reservation_natural_keys) == len(set(reservation_natural_keys)),
            'Chave natural composta (person_id, establishment, scheduled_at) repetida em reservations')
    linked = Counter()
    visit_natural_keys = []
    for row in records['visits']:
        require(positive(row['person_id']) and row['person_id'] in people, 'Pessoa da visita inexistente')
        require(positive(row['party_size']), 'Grupo da visita invalido')
        source, cultural = row['establishment_source_id'], row['cultural_place_id']
        require((source is None) != (cultural is None), 'Visita deve ter exatamente um destino')
        require(source in source_ids if source is not None else cultural in cultural_ids,
                'Destino da visita inexistente')
        visited = instant(row['visited_at'])
        require(visited <= cutoff, 'Visita futura na data de referencia')
        visit_natural_keys.append((row['person_id'], visited))
        reservation_id = row['reservation_id']
        if reservation_id is not None:
            require(positive(reservation_id) and reservation_id in reservations, 'Reserva da visita inexistente')
            reservation = reservations[reservation_id]
            require(reservation['status'] == 'fulfilled', 'Visita ligada a reserva nao cumprida')
            require((row['person_id'], source, row['party_size']) ==
                    (reservation['person_id'], reservation['establishment_source_id'], reservation['party_size']),
                    'Pessoa, destino ou grupo diferentes da reserva')
            require(visited >= instant(reservation['created_at']), 'Visita anterior a criacao da reserva')
            linked[reservation_id] += 1
    require(len(visit_natural_keys) == len(set(visit_natural_keys)),
            'Chave natural composta (person_id, visited_at) repetida em visits')
    require(all(linked[key] == (1 if row['status'] == 'fulfilled' else 0)
                for key, row in reservations.items()), 'Reservas e visitas cumpridas nao correspondem')
    return records


def prepare_activity():
    catalogue = prepare()
    provenance = json.loads((ROOT/'data/provenance.json').read_text(encoding='utf-8'))
    original_xml = ROOT.parent/'Fontes/Camara_Municipal/79922_2.xml'
    expected_xml_hash = provenance['culture']['sha256']
    require(sha256(XML_PATH) == sha256(original_xml) == expected_xml_hash, 'XML diferente da fonte preservada')
    places = ET.parse(XML_PATH).getroot().findall('place')
    cultural_ids = [place.attrib['id'] for place in places]
    require(len(cultural_ids) == len(set(cultural_ids)), 'IDs culturais repetidos')
    with SOURCE.open(encoding='utf-8-sig', newline='') as handle:
        source_ids = {row['restaurant_link'] for row in csv.DictReader(handle)}
    scenario = json.loads(FIXTURE.read_text(encoding='utf-8'))
    records = validate(scenario, source_ids, set(cultural_ids))

    def establishment(source_id):
        if source_id is None:
            return 'NULL'
        return '(SELECT establishment_id FROM tiago_lab.establishment WHERE source_id = ' + sql_text(source_id) + ')'

    guard = ("DO $activity_guard$ BEGIN IF "
             f"(SELECT count(*) FROM tiago_lab.establishment) <> {catalogue['expected_counts']['establishment']} "
             'OR EXISTS (SELECT 1 FROM tiago_lab.person) '
             'OR EXISTS (SELECT 1 FROM tiago_lab.reservation) '
             'OR EXISTS (SELECT 1 FROM tiago_lab.visit) THEN '
             "RAISE EXCEPTION 'Catalogo inesperado ou atividade ja existente' USING ERRCODE = 'P0001'; "
             'END IF; END $activity_guard$;')
    statements = ['BEGIN;', 'SET LOCAL standard_conforming_strings = on;', guard]
    for section, table, columns in (
        ('people', 'person', 'person_id, display_name, contact_phone, is_synthetic'),
        ('reservations', 'reservation', 'reservation_id, person_id, establishment_id, created_at, scheduled_at, party_size, status, is_synthetic'),
        ('visits', 'visit', 'visit_id, person_id, establishment_id, cultural_place_id, reservation_id, visited_at, party_size, is_synthetic'),
    ):
        tuples = []
        for row in records[section]:
            values = []
            for field in COLUMNS[section]:
                value = row[field]
                if field == 'establishment_source_id':
                    values.append(establishment(value))
                elif value is None:
                    values.append('NULL')
                elif type(value) is int:
                    values.append(str(value))
                else:
                    values.append(sql_text(value))
            tuples.append('(' + ', '.join(values + ['true']) + ')')
        require(bool(tuples), 'Secao vazia: ' + section)
        statements.append(f'INSERT INTO tiago_lab.{table} ({columns}) VALUES\n' + ',\n'.join(tuples) + ';')
    statements.append('COMMIT;')
    ACTIVITY_SQL.write_text('\n'.join(statements) + '\n', encoding='utf-8', newline='\n')
    manifest = {
        'generated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'scenario_as_of': scenario['scenario_as_of'], 'is_synthetic': True,
        'fixture_sha256': sha256(FIXTURE), 'xml_sha256': expected_xml_hash,
        'catalogue_sql_sha256': catalogue['sql_sha256'], 'sql_sha256': sha256(ACTIVITY_SQL),
        'expected_counts': {table: len(records[section]) for table, section in
                            (('person', 'people'), ('reservation', 'reservations'), ('visit', 'visits'))},
        'reservation_status_counts': dict(Counter(row['status'] for row in records['reservations'])),
        'cultural_visits': sum(row['cultural_place_id'] is not None for row in records['visits']),
        'limits': 'Small deterministic fictional scenario; not representative of real demand. XML references validated outside PostgreSQL.',
    }
    ACTIVITY_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    print(json.dumps(prepare_activity(), ensure_ascii=False, indent=2))
