"""Prepara SQL transacional do catalogo completo sem aceder a uma base existente."""
from datetime import datetime
from decimal import Decimal
import csv
import hashlib
import json

from profile_source import ROOT, SOURCE, analyse

OUTPUT = ROOT/'postgresql/generated'
SQL_PATH = OUTPUT/'full_catalogue.sql'
MANIFEST_PATH = OUTPUT/'full_catalogue_manifest.json'
SCHEMA_PATH = ROOT/'postgresql/01_schema.sql'
SAMPLE_PATH = ROOT/'data/provenance.json'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sql_text(value):
    if value is None:
        return 'NULL'
    if '\x00' in value:
        raise ValueError('PostgreSQL text nao aceita NUL')
    return "'" + value.replace("'", "''") + "'"


def sql_number(value, integral=False):
    if not value.strip():
        return 'NULL'
    number = Decimal(value)
    if integral:
        if number != number.to_integral_value():
            raise ValueError('Contagem fracionaria nao pode ser convertida para inteiro')
        return str(int(number))
    return format(number, 'f')


def prepare():
    report = analyse(SOURCE)
    provenance = json.loads((SOURCE.parent/'provenance.json').read_text(encoding='utf-8'))
    if report['source_sha256'] != provenance['lisbon_extract']['sha256']:
        raise ValueError('A fonte nao corresponde ao SHA-256 preservado')
    if report['blocking_rows']:
        raise ValueError(f"Fonte com {report['blocking_rows']} registos bloqueados; executar profile_source.py")
    with SOURCE.open(encoding='utf-8-sig', newline='') as handle:
        rows = {row['restaurant_link']: row for row in csv.DictReader(handle)}
    sample = json.loads(SAMPLE_PATH.read_text(encoding='utf-8'))
    sample_ids = sample['tripadvisor']['source_ids']
    if len(sample_ids) != len(set(sample_ids)) or not set(sample_ids) <= rows.keys():
        raise ValueError('IDs da amostra repetidos ou ausentes do catalogo')
    ordered_ids = sample_ids + sorted(set(rows) - set(sample_ids))
    mapping = {source_id: index for index, source_id in enumerate(ordered_ids, 1)}
    establishments = []
    labels = []
    for source_id, establishment_id in mapping.items():
        row = rows[source_id]
        values = [str(establishment_id), sql_text(source_id), sql_text(row['restaurant_name']),
                  sql_text(row['address'] or None), sql_number(row['latitude']),
                  sql_number(row['longitude']), sql_number(row['avg_rating']),
                  sql_number(row['total_reviews_count'], integral=True)]
        establishments.append('(' + ', '.join(values) + ')')
        for label in sorted({part.strip() for part in row['cuisines'].split(',') if part.strip()}):
            labels.append(f'({establishment_id}, {sql_text(label)})')
    schema_lines = SCHEMA_PATH.read_text(encoding='utf-8').splitlines()
    if schema_lines.count('BEGIN;') != 1 or schema_lines.count('COMMIT;') != 1:
        raise ValueError('Rever delimitacao transacional de 01_schema.sql')
    schema = '\n'.join(line for line in schema_lines if line not in ('BEGIN;', 'COMMIT;'))
    statements = ['BEGIN;', 'SET LOCAL standard_conforming_strings = on;', schema,
                  'INSERT INTO tiago_lab.establishment '
                  '(establishment_id, source_id, name, address, latitude, longitude, average_rating, review_count) VALUES\n'
                  + ',\n'.join(establishments) + ';']
    if labels:
        statements.append('INSERT INTO tiago_lab.establishment_label (establishment_id, label) VALUES\n'
                          + ',\n'.join(labels) + ';')
    statements.append('COMMIT;')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    SQL_PATH.write_text('\n'.join(statements) + '\n', encoding='utf-8', newline='\n')
    manifest = {
        'generated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'source_file': str(SOURCE.relative_to(ROOT.parent)),
        'source_sha256': report['source_sha256'],
        'schema_sha256': sha256(SCHEMA_PATH),
        'sample_provenance_sha256': sha256(SAMPLE_PATH),
        'sql_file': str(SQL_PATH.relative_to(ROOT)), 'sql_sha256': sha256(SQL_PATH),
        'expected_counts': {'establishment': len(establishments),
                            'establishment_label': len(labels),
                            'person': 0, 'reservation': 0, 'visit': 0},
        'id_policy': 'Sample IDs 1..8 preserved; remaining source IDs sorted lexicographically. Rebuilding from a changed source may change other local IDs.',
        'preserved_sample_ids': {source_id: mapping[source_id] for source_id in sample_ids},
        'scope': 'Real historical catalogue only. No synthetic activity imported.',
        'geographic_policy': 'Original coordinates retained, including questionable cases; no municipal filter or imputation.',
        'null_policy': 'Blank numeric fields and blank addresses become NULL. No fabricated labels.',
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    print(json.dumps(prepare(), ensure_ascii=False, indent=2))
