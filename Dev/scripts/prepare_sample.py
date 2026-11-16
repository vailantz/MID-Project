"""Prepara uma amostra real + cenario sintetico pequeno, sem ler o SQL anterior."""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MID = ROOT.parents[1]
IDS = [
    'g189158-d10002838', 'g189158-d10003138', 'g189158-d10005260',
    'g189158-d10005571', 'g189158-d10044675', 'g189158-d10130339',
    'g189158-d10003850', 'g189158-d10087956',
]


def quote(value):
    if value is None or value == '':
        return 'NULL'
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert(table, columns, rows):
    return f'INSERT INTO tiago_lab.{table} ({columns}) VALUES\n' + ',\n'.join(
        '(' + ', '.join(quote(v) for v in row) + ')' for row in rows
    ) + ';\n'


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-zip', type=Path,
        default=MID/'Projeto/Fontes/Tripadvisor_Kaggle/tripadvisor_european_restaurants.zip')
    parser.add_argument('--culture-xml', type=Path,
        default=MID/'Projeto/Fontes/Camara_Municipal/79922_2.xml')
    args = parser.parse_args()
    data = ROOT/'data'; data.mkdir(exist_ok=True)
    selected = {}
    with zipfile.ZipFile(args.source_zip) as z:
        csv_name = next(n for n in z.namelist() if n.lower().endswith('.csv'))
        with z.open(csv_name) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig', newline=''))
            for row in reader:
                key = row['restaurant_link']
                if key in IDS:
                    if key in selected:
                        raise ValueError(f'Duplicate source key: {key}')
                    assert row['city'] == 'Lisbon' and row['country'] == 'Portugal'
                    selected[key] = row
    assert set(selected) == set(IDS), 'Missing sample establishments'
    rows = [selected[k] for k in IDS]
    raw_path = data/'tripadvisor_sample_original.json'
    raw_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    # JSON e apenas a preservacao dos oito registos CSV. B1 e implementada em SQL.
    xml_path = data/'cultural_catalogue.xml'
    shutil.copyfile(args.culture_xml, xml_path)
    tree = ET.parse(xml_path)
    museum = tree.find("./place[@category='museum']").attrib['id']
    monument = tree.find("./place[@category='monument']").attrib['id']

    establishments = []
    labels = []
    for i, row in enumerate(rows, 1):
        num = lambda k: float(row[k]) if row[k] else None
        establishments.append((i, row['restaurant_link'], row['restaurant_name'],
            row['address'], num('latitude'), num('longitude'), num('avg_rating'),
            int(float(row['total_reviews_count'])) if row['total_reviews_count'] else None))
        labels.extend((i, label) for label in sorted(set(
            p.strip() for p in row['cuisines'].split(',') if p.strip())))
    persons = [(1,'Ana Exemplo'), (2,'Bruno Exemplo'), (3,'Ana Exemplo'),
               (4,'Carla Exemplo'), (5,'Diogo Exemplo'), (6,'Eva Exemplo')]
    # Casos manuais deterministas: nomes iguais, cancelamento, no-show, futuro,
    # visitas sem reserva, visitas culturais e limite exato de mes.
    bookings = [
        (101,1,1,'2026-09-09 10:00+01','2026-09-10 20:00+01',2,'fulfilled'),
        (102,2,1,'2026-09-10 10:00+01','2026-09-12 20:00+01',4,'cancelled'),
        (103,1,3,'2026-09-13 10:00+01','2026-09-15 20:00+01',3,'fulfilled'),
        (104,3,3,'2026-09-15 10:00+01','2026-09-17 20:00+01',2,'no_show'),
        (105,4,4,'2026-09-16 10:00+01','2026-09-18 12:00+01',1,'fulfilled'),
        (106,5,6,'2026-10-20 10:00+01','2026-10-25 20:00+00',4,'confirmed'),
        (107,2,8,'2026-09-20 10:00+01','2026-09-22 20:00+01',2,'fulfilled'),
    ]
    visits = [
        (1001,1,1,None,101,'2026-09-10 20:00+01',2),
        (1002,1,3,None,103,'2026-09-15 20:00+01',3),
        (1003,4,4,None,105,'2026-09-18 12:00+01',1),
        (1004,2,8,None,107,'2026-09-22 20:00+01',2),
        (1005,3,1,None,None,'2026-09-20 20:00+01',1),
        (1006,2,1,None,None,'2026-09-24 20:00+01',4),
        (1007,3,5,None,None,'2026-09-28 20:00+01',2),
        (1008,1,None,museum,None,'2026-09-11 14:00+01',2),
        (1009,2,None,museum,None,'2026-09-25 14:00+01',4),
        (1010,3,None,monument,None,'2026-09-29 14:00+01',2),
        (1011,5,6,None,None,'2026-10-10 20:00+01',2),
        (1012,1,1,None,None,'2026-10-01 00:00+01',1),
    ]
    sql = '-- Dados reais do catalogo 2021; pessoas, reservas e visitas SINTETICAS.\nBEGIN;\n'
    sql += insert('establishment','establishment_id,source_id,name,address,latitude,longitude,average_rating,review_count',establishments)
    sql += insert('establishment_label','establishment_id,label',labels)
    sql += insert('person','person_id,display_name',persons)
    sql += insert('reservation','reservation_id,person_id,establishment_id,created_at,scheduled_at,party_size,status',bookings)
    sql += insert('visit','visit_id,person_id,establishment_id,cultural_place_id,reservation_id,visited_at,party_size',visits)
    sql += 'COMMIT;\n'
    (ROOT/'postgresql/02_sample_data.sql').write_text(sql,encoding='utf-8')
    metadata = {
        'prepared_on':'2026-10-21', 'synthetic_scenario_as_of':'2026-10-21',
        'source_sql_previous_zip_used':False,
        'tripadvisor': {
            'catalogue':'https://www.kaggle.com/datasets/stefanoleone992/tripadvisor-european-restaurants',
            'original_format':'CSV in ZIP', 'snapshot':'May 2021',
            'licence':'CC0 according to publisher; retained from accepted proposal',
            'original_access_date':'2026-10-14',
            'local_archive_sha256':sha256(args.source_zip),
            'csv_member':csv_name, 'selection':'Eight fixed IDs, educational purposive sample',
            'source_ids':IDS, 'sample_sha256':sha256(raw_path),
            'caveat':'cuisines mixes cuisine and venue-type labels; no exclusive category inferred',
        },
        'culture': {
            'input':'Approved proposal XML, unchanged copy; municipal ArcGIS origins retained inside XML',
            'sha256':sha256(xml_path), 'records':len(tree.findall('place')),
            'museum_records':len(tree.findall("./place[@category='museum']")),
            'monument_records':len(tree.findall("./place[@category='monument']")),
        },
        'sample_counts': {'establishment':len(rows),'establishment_label':len(labels),
            'person':len(persons),'reservation':len(bookings),'visit':len(visits)},
        'synthetic_rules': {
            'method':'Manually specified deterministic fixtures, no random generator',
            'persons':'All fictional; same display_name does not imply same person',
            'reservations':'All simulated, including fulfilled, cancelled, no_show and future confirmed',
            'visits':'All simulated; includes walk-ins and culture. No claim about real visits.',
            'party_size':'Includes the named person and unnamed companions; not unique visitor count',
            'time_zone':'Europe/Lisbon; explicit offsets in fixtures; September is UTC+01',
        },
        'culture_demo_ids':{'museum':museum,'monument':monument},
    }
    (data/'provenance.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(metadata['sample_counts']))


if __name__ == '__main__':
    main()
