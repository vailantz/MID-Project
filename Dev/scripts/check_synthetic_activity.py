"""Verificacoes da atividade ficticia na instancia isolada da P1."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import csv
import json
import xml.etree.ElementTree as ET

from prepare_synthetic_activity import ROOT, SOURCE, FIXTURE, XML_PATH, COLUMNS, instant


def verify_activity(query, check):
    scenario = json.loads(FIXTURE.read_text(encoding='utf-8'))
    records = {section: [dict(zip(columns, row, strict=True)) for row in scenario[section]]
               for section, columns in COLUMNS.items()}
    queries = {
        'people': 'SELECT person_id, display_name, contact_phone, is_synthetic FROM tiago_lab.person ORDER BY person_id',
        'reservations': 'SELECT r.reservation_id, r.person_id, e.source_id AS establishment_source_id, '
                        'r.created_at::text, r.scheduled_at::text, r.party_size, r.status, r.is_synthetic '
                        'FROM tiago_lab.reservation r JOIN tiago_lab.establishment e USING (establishment_id) '
                        'ORDER BY r.reservation_id',
        'visits': 'SELECT v.visit_id, v.person_id, e.source_id AS establishment_source_id, '
                  'v.cultural_place_id, v.reservation_id, v.visited_at::text, v.party_size, v.is_synthetic '
                  'FROM tiago_lab.visit v LEFT JOIN tiago_lab.establishment e USING (establishment_id) '
                  'ORDER BY v.visit_id',
    }
    for section, statement in queries.items():
        actual = query(statement)
        expected = [dict(row, is_synthetic=True) for row in records[section]]
        for collection in (actual, expected):
            for row in collection:
                for field in ('created_at', 'scheduled_at', 'visited_at'):
                    if field in row:
                        row[field] = instant(row[field])
        check('activity_exact_values_' + section, actual == expected)
    quality = (ROOT/'postgresql/04_quality.sql').read_text(encoding='utf-8')
    quality = '\n'.join(line for line in quality.splitlines() if not line.lstrip().startswith('--'))
    for index, statement in enumerate(filter(str.strip, quality.split(';')), 1):
        check('activity_quality_' + str(index), query(statement) == [])
    cultural_ids = {place.attrib['id'] for place in ET.parse(XML_PATH).getroot().findall('place')}
    cultural = query('SELECT cultural_place_id FROM tiago_lab.visit WHERE cultural_place_id IS NOT NULL')
    check('activity_external_xml_references', len(cultural) == 7
          and all(row['cultural_place_id'] in cultural_ids for row in cultural))
    check('activity_homonyms_not_merged', query("SELECT person_id FROM tiago_lab.person "
          "WHERE display_name='Ana Exemplo' ORDER BY person_id") == [{'person_id': 1}, {'person_id': 3}])
    check('activity_shared_phone_not_merged', query("SELECT person_id FROM tiago_lab.person "
          "WHERE contact_phone='+351910000002' ORDER BY person_id") == [{'person_id': 2}, {'person_id': 4}])
    check('activity_repeated_reservations', query("SELECT count(*) n FROM tiago_lab.reservation r "
          'JOIN tiago_lab.establishment e USING (establishment_id) '
          "WHERE r.person_id=7 AND e.source_id='g189158-d10466969'") == [{'n': 2}])
    statements = (ROOT/'postgresql/06_p1_activity_queries.sql').read_text(encoding='utf-8').split(';')
    simple, monthly, complex_query = [query(statement) for statement in statements if statement.strip()]
    with SOURCE.open(encoding='utf-8-sig', newline='') as handle:
        source = {row['restaurant_link']: row for row in csv.DictReader(handle)}
    sushi = {key for key, row in source.items() if row['avg_rating']
             and Decimal(row['avg_rating']) >= 4
             and 'Sushi' in {part.strip() for part in row['cuisines'].split(',')}}
    check('activity_simple_query_complete', len(simple) == len(sushi)
          and {row['source_id'] for row in simple} == sushi)
    expected_month = defaultdict(lambda: [0, 0])
    start, end = instant('2026-09-01T00:00:00+01:00'), instant('2026-10-01T00:00:00+01:00')
    for visit in records['visits']:
        if visit['establishment_source_id'] and start <= instant(visit['visited_at']) < end:
            expected_month[visit['establishment_source_id']][0] += 1
            expected_month[visit['establishment_source_id']][1] += visit['party_size']
    check('activity_monthly_query_including_zeros', len(monthly) == len(source)
          and {row['source_id'] for row in monthly} == source.keys()
          and all([row['visit_events'], row['simulated_attendances']] == expected_month[row['source_id']]
                  for row in monthly))
    check('activity_monthly_expected_totals', sum(row['visit_events'] for row in monthly) == 19
          and sum(row['simulated_attendances'] for row in monthly) == 42
          and sum(row['visit_events'] == 0 for row in monthly) == 5252)
    check('activity_complex_query', complex_query == [
        {'source_id': 'g189158-d10002838', 'name': 'Miss Jappa', 'distinct_registered_people': 3,
         'simulated_attendances': 7},
        {'source_id': 'g189158-d10466969', 'name': 'Miyagi Sushi', 'distinct_registered_people': 3,
         'simulated_attendances': 10}])
    check('activity_month_boundary', query("SELECT visit_id FROM tiago_lab.visit "
          "WHERE visit_id IN (1012,1020) AND visited_at >= TIMESTAMPTZ '2026-09-01 00:00:00 Europe/Lisbon' "
          "AND visited_at < TIMESTAMPTZ '2026-10-01 00:00:00 Europe/Lisbon'") == [{'visit_id': 1020}])
    summary = {'executed_at': datetime.now().astimezone().isoformat(timespec='seconds'),
               'scenario_as_of': scenario['scenario_as_of'], 'is_synthetic_activity': True,
               'q1_sushi_rating': simple,
               'q2_total_establishments': len(monthly),
               'q2_zero_visit_establishments': sum(row['visit_events'] == 0 for row in monthly),
               'q2_only_nonzero_rows': [row for row in monthly if row['visit_events']],
               'q2_visit_events': sum(row['visit_events'] for row in monthly),
               'q2_simulated_attendances': sum(row['simulated_attendances'] for row in monthly),
               'q3_distinct_registered_people': complex_query}
    (ROOT/'results/p1_activity_queries.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary
