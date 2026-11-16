"""Prepara e verifica a fonte XML/BaseX P1, sem iniciar PostgreSQL."""
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
import shutil
import tempfile

from lxml import etree
from check_demo import run

ROOT = Path(__file__).resolve().parents[1]
XML_PATH = ROOT/'data/cultural_catalogue.xml'
ORIGINAL = ROOT.parent/'Fontes/Camara_Municipal/79922_2.xml'
XSD_PATH = ROOT/'xml_basex/catalogue.xsd'
JAR = ROOT/'tools/BaseX124.jar'
DATABASE = 'tiago_culture_p1'
JAR_HASH = '3975bc91acfadd1c139872dd9fc154f2fc7a166792509c7665501089edf5e301'
NIL = '{http://www.w3.org/2001/XMLSchema-instance}nil'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(node):
    text = '' if node is None else ''.join(node.itertext())
    return re.sub(r'[ \t\r\n]+', ' ', text).strip(' ')


def usable(node):
    return node is not None and node.get(NIL) not in ('true', '1') and normalize(node) not in ('', '-')


def assert_dbpath(state):
    configuration = state/'.basex'
    if configuration.exists():
        entries = [line.split('=', 1)[1].strip() for line in configuration.read_text(encoding='utf-8').splitlines()
                   if re.match(r'^DBPATH\s*=', line)]
        if len(entries) != 1 or Path(entries[0]).resolve() != (state/'data').resolve():
            raise ValueError('DBPATH inesperado; nenhuma base foi aberta ou substituida')


def basex(java, state, expression=None, query_file=None, context=None):
    state.mkdir(parents=True, exist_ok=True)
    assert_dbpath(state)
    command = [java, f'-Dorg.basex.path={state}', '-cp', JAR, 'org.basex.BaseX']
    if expression is not None:
        query_file = state/'command.xq'
        query_file.write_text(expression, encoding='utf-8', newline='\n')
    if context is not None:
        command.extend(['-i', context])
    value = run(command + ['-Q', query_file])
    assert_dbpath(state)
    return value


def ensure_database(java, state):
    basex(java, state, expression='<ready/>')
    existed = etree.fromstring(basex(java, state,
        expression=f'<exists>{{db:exists("{DATABASE}")}}</exists>').encode()).text == 'true'
    if not existed:
        uri = XML_PATH.as_uri().replace("'", "''")
        basex(java, state, expression=f"db:create('{DATABASE}', doc('{uri}'), 'catalogue.xml')")
    uri = XML_PATH.as_uri().replace("'", "''")
    equal = etree.fromstring(basex(java, state, expression=
        f"<matches>{{deep-equal(db:get('{DATABASE}')/culturalCatalogue, doc('{uri}')/culturalCatalogue)}}</matches>").encode())
    if equal.text != 'true':
        raise ValueError('A base BaseX diverge do XML preservado. Nenhuma base foi apagada ou substituida; escolher outro --state.')
    return existed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java', default=shutil.which('java') or 'java')
    parser.add_argument('--state', type=Path, default=ROOT/'.runtime/basex_p1')
    args = parser.parse_args()
    runtime = (ROOT/'.runtime').resolve()
    state = args.state.resolve()
    if state == runtime or not state.is_relative_to(runtime) or state.is_relative_to(runtime/'basex'):
        parser.error('--state deve ser uma subpasta de Dev/.runtime, separada do estado basex da aula')
    output = ROOT/'results/basex_p1'
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    report = {'status': 'running', 'executed_at': datetime.now().astimezone().isoformat(timespec='seconds'),
              'database': DATABASE, 'state': str(state), 'checks': checks, 'postgresql_started': False}

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    print('A verificar o XML, o XSD e as dependencias...', flush=True)
    try:
        provenance = json.loads((ROOT/'data/provenance.json').read_text(encoding='utf-8'))
        expected_hash = provenance['culture']['sha256']
        check('approved_xml_hash_and_working_copy', sha256(XML_PATH) == sha256(ORIGINAL) == expected_hash)
        check('pinned_basex_12_4_jar', sha256(JAR) == JAR_HASH)
        preserved = [XML_PATH, ORIGINAL, XSD_PATH, ROOT/'data/synthetic_activity.json']
        before = {str(path): sha256(path) for path in preserved}
        safe = etree.XMLParser(resolve_entities=False, no_network=True)
        document = etree.parse(str(XML_PATH), safe)
        schema = etree.XMLSchema(etree.parse(str(XSD_PATH), safe))
        schema.assertValid(document)
        check('original_xml_valid_against_project_xsd', True)
        root = document.getroot()
        places = root.findall('place')
        check('expected_record_and_category_counts', Counter(place.get('category') for place in places)
              == {'museum': 67, 'monument': 63})
        invalid_cases = []
        for field, value in (('name', ' '), ('location/latitude', '95'),
                             ('location/longitude', '-181')):
            altered = copy.deepcopy(document)
            altered.getroot().find('place/' + field).text = value
            invalid_cases.append(('xsd_reject_' + field.replace('/', '_'), altered))
        altered = copy.deepcopy(document)
        altered.getroot().find('place').remove(altered.getroot().find('place/name'))
        invalid_cases.append(('xsd_reject_missing_name', altered))
        altered = copy.deepcopy(document)
        items = altered.getroot().findall('place')
        items[1].set('id', items[0].get('id'))
        invalid_cases.append(('xsd_reject_duplicate_id', altered))
        for attribute, value in (('sourceRef', 'unknown'), ('category', 'unknown')):
            altered = copy.deepcopy(document)
            altered.getroot().find('place').set(attribute, value)
            invalid_cases.append(('xsd_reject_' + attribute, altered))
        for attribute, value in (('coordinateSystem', 'unknown'), ('generatedOn', 'not-a-date')):
            altered = copy.deepcopy(document)
            altered.getroot().set(attribute, value)
            invalid_cases.append(('xsd_reject_' + attribute, altered))
        altered = copy.deepcopy(document)
        telephone = altered.getroot().find('place/contact/telephone')
        telephone.set(NIL, 'true')
        telephone.text = 'invalid'
        invalid_cases.append(('xsd_reject_nil_with_content', altered))
        for name, altered in invalid_cases:
            check(name, not schema.validate(altered))
        print('XML e XSD verificados. A preparar ou reutilizar a base BaseX...', flush=True)
        report['reused_existing_database'] = ensure_database(args.java, state)
        check('database_matches_approved_xml', True)
        check('repeat_preparation_reuses_matching_database', ensure_database(args.java, state))
        values = {}
        for query_file in sorted((ROOT/'xml_basex').glob('*.xq')):
            print(f'A executar {query_file.name}...', flush=True)
            value = basex(args.java, state, query_file=query_file, context=DATABASE)
            (output/(query_file.stem + '.xml')).write_text(value, encoding='utf-8', newline='\n')
            values[query_file.stem] = etree.fromstring(value.encode('utf-8'))
        museums = {place.get('id'): normalize(place.find('name')) for place in places if place.get('category') == 'museum'}
        actual_museums = {item.get('id'): normalize(item) for item in values['01_museums']}
        check('simple_museum_query_exact', len(values['01_museums']) == 67 and actual_museums == museums)
        check('intermediate_count_query', {item.get('name'): int(item.get('count')) for item in values['02_counts']}
              == {'museum': 67, 'monument': 63})
        expected_interface = {place.get('id'): (place.get('category'), normalize(place.find('name')),
                              Decimal(place.findtext('location/latitude')), Decimal(place.findtext('location/longitude')))
                              for place in places}
        actual_interface = {place.get('id'): (place.get('category'), normalize(place.find('name')),
                            Decimal(place.findtext('latitude')), Decimal(place.findtext('longitude')))
                            for place in values['03_cultural_interface']}
        check('complete_cultural_interface', len(values['03_cultural_interface']) == 130 and actual_interface == expected_interface)
        quality = values['04_quality']
        check('basic_quality_no_blockers', all(quality.get(field) == '0' for field in
              ('duplicateIds', 'missingNames', 'unknownCategories', 'missingSourceReferences')) and len(quality) == 0)
        extended = values['06_p1_quality']
        check('semantic_quality_no_blockers', all(extended.get(field) == '0' for field in
              ('categorySourceMismatches', 'idPrefixMismatches', 'invalidNilValues')))
        profiles = {}
        for field in ('telephone', 'fax', 'email', 'website', 'description'):
            statuses = Counter()
            for place in places:
                node = place.find(field if field == 'description' else 'contact/' + field)
                status = ('missing' if node is None else 'nil' if node.get(NIL) in ('true', '1') else
                          'blank' if not normalize(node) else 'placeholder' if normalize(node) == '-' else 'usable')
                statuses[status] += 1
            expected = {key: statuses[key] for key in ('missing', 'nil', 'blank', 'placeholder', 'usable')}
            profiles[field] = expected
            actual = extended.find(f"fields/field[@name='{field}']")
            check('field_profile_' + field, actual is not None and
                  {key: int(actual.get(key)) for key in expected} == expected)
        sources = {source.get('id'): source for source in root.findall('sources/source')}
        expected_contacts = {}
        for place in places:
            contacts = {field: normalize(place.find('contact/' + field)) for field in ('telephone', 'email', 'website')
                        if usable(place.find('contact/' + field))}
            if contacts and usable(place.find('description')):
                source = sources[place.get('sourceRef')]
                expected_contacts[place.get('id')] = (place.get('category'), place.get('sourceRef'), normalize(place.find('name')),
                    contacts, normalize(place.find('description')), source.get('provider'), source.get('accessDate'), source.findtext('catalogueUrl'))
        actual_contacts = {place.get('id'): (place.get('category'), place.get('sourceRef'), normalize(place.find('name')),
            {node.tag: normalize(node) for node in place.find('contacts')}, normalize(place.find('description')),
            place.find('provenance').get('provider'), place.find('provenance').get('accessDate'),
            place.findtext('provenance/catalogueUrl')) for place in values['05_contactable_places']}
        check('complex_contact_and_provenance_query', len(actual_contacts) == len(values['05_contactable_places'])
              and actual_contacts == expected_contacts)
        names = Counter(normalize(place.find('name')) for place in places)
        repeated = {name: count for name, count in names.items() if count > 1}
        check('repeated_names_reported_not_merged', {node.get('value'): int(node.get('records'))
              for node in extended.findall('repeatedNames/name')} == repeated)
        print('Consultas verificadas. A testar incoerencias em copias do XML...', flush=True)
        tests_state = Path(tempfile.mkdtemp(prefix='basex_p1_test_', dir=runtime))
        for attribute, value, metric in (('sourceRef', 'monument', 'categorySourceMismatches'),
                                       ('id', 'monument:test-mismatch', 'idPrefixMismatches')):
            altered = copy.deepcopy(document)
            altered.getroot().find('place').set(attribute, value)
            check('xsd_accepts_semantic_case_' + attribute, schema.validate(altered))
            altered_path = tests_state/('altered_' + attribute + '.xml')
            altered_path.write_bytes(etree.tostring(altered, encoding='utf-8', xml_declaration=True))
            result = etree.fromstring(basex(args.java, state, query_file=ROOT/'xml_basex/06_p1_quality.xq', context=altered_path).encode())
            check('xquery_detects_semantic_case_' + attribute, result.get(metric) == '1')
        print('A testar a detecao de uma base desatualizada, sem alterar a base P1...', flush=True)
        ensure_database(args.java, tests_state)
        basex(args.java, tests_state, expression=f"replace value of node db:get('{DATABASE}')/culturalCatalogue/place[1]/name with 'STALE TEST'")
        try:
            ensure_database(args.java, tests_state)
        except ValueError as error:
            check('stale_database_detected_without_replacement', 'diverge' in str(error))
        else:
            raise AssertionError('Base divergente aceite')
        print('A verificar referencias culturais e integridade dos ficheiros...', flush=True)
        scenario = json.loads((ROOT/'data/synthetic_activity.json').read_text(encoding='utf-8'))
        references = [dict(zip(scenario['columns']['visits'], row, strict=True))['cultural_place_id']
                      for row in scenario['visits']]
        references = [reference for reference in references if reference is not None]
        check('synthetic_cultural_targets_resolve_in_basex', len(references) == 7
              and all(reference in actual_interface for reference in references))
        check('unknown_cultural_target_detected', 'museum:unknown' not in actual_interface)
        check('original_xml_xsd_and_scenario_unchanged', before == {str(path): sha256(path) for path in preserved})
        report.update(status='passed', checks_passed=len(checks), xml_sha256=expected_hash,
                      xsd_sha256=sha256(XSD_PATH), basex_jar_sha256=JAR_HASH,
                      counts={'museum': 67, 'monument': 63}, contactable_places=len(actual_contacts),
                      field_profiles=profiles, repeated_names=repeated, synthetic_cultural_visits_checked=len(references),
                      limits=['Project XSD does not validate raw sourceFields individually.',
                              'Structural validity and usable contact text do not establish real-world truth or current availability.',
                              'Names are not identities. No deduplication or PostgreSQL queries performed.'])
        print(f'PASS: {len(checks)} verificacoes BaseX; 67 museus, 63 monumentos; {len(actual_contacts)} registos com contacto e descricao.', flush=True)
    except Exception as error:
        report.update(status='failed', error=str(error), checks_passed=len(checks))
        raise
    finally:
        report['finished_at'] = datetime.now().astimezone().isoformat(timespec='seconds')
        (output/'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
