"""Carrega e verifica o catalogo numa instancia PostgreSQL nova e isolada."""
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import argparse
import csv
import json
import os
import socket
import tempfile

from check_demo import run
from prepare_full_catalogue import ROOT, SOURCE, SQL_PATH, prepare, sha256, sql_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pg-bin', type=Path, default=Path(r'C:\Program Files\PostgreSQL\16\bin'))
    parser.add_argument('--port', type=int, default=55441)
    parser.add_argument('--keep-open', action='store_true',
                        help='Manter a base aberta ate carregar Enter neste terminal')
    parser.add_argument('--with-activity', action='store_true',
                        help='Carregar e verificar tambem o cenario ficticio da P1')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or args.port == 55439:
        parser.error('Escolher uma porta valida diferente da porta 55439 da amostra')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1', args.port)) == 0:
            parser.error(f'Porta {args.port} ocupada. Nenhum servidor foi alterado; usar --port.')
    for executable in ('initdb', 'pg_ctl', 'psql', 'createdb'):
        if not (args.pg_bin/(executable + '.exe')).is_file():
            parser.error(f'Executavel em falta: {executable}; rever --pg-bin')
    os.environ['PGCLIENTENCODING'] = 'UTF8'
    preserved_files = [SOURCE, ROOT/'postgresql/01_schema.sql',
                       ROOT/'postgresql/02_sample_data.sql', ROOT/'data/provenance.json']
    activity = None
    if args.with_activity:
        from prepare_synthetic_activity import prepare_activity, ACTIVITY_SQL, FIXTURE, XML_PATH
        from check_synthetic_activity import verify_activity
        activity = prepare_activity()
        preserved_files.extend([FIXTURE, XML_PATH, ROOT.parent/'Fontes/Camara_Municipal/79922_2.xml'])
    before = {str(path): sha256(path) for path in preserved_files}
    manifest = prepare()
    regenerated = prepare()
    if manifest['sql_sha256'] != regenerated['sql_sha256']:
        raise AssertionError('Geracao SQL nao deterministica')
    cluster = Path(tempfile.mkdtemp(prefix='dmi_pg_p1_'))/'data'
    executable = lambda name: args.pg_bin/(name + '.exe')
    client = [executable('psql'), '-X', '-w', '-h', '127.0.0.1', '-p', str(args.port),
              '-U', 'dmi_p1', '-v', 'ON_ERROR_STOP=1', '-v', 'VERBOSITY=verbose']
    connection = ['-h', '127.0.0.1', '-p', str(args.port), '-U', 'dmi_p1', '-w']
    checks = ['deterministic_sql_generation']
    result = {'status': 'running',
              'executed_at': datetime.now().astimezone().isoformat(timespec='seconds'),
              'cluster': str(cluster), 'port': args.port, 'database': 'tiago_p1',
              'source_sha256': manifest['source_sha256'],
              'sql_sha256': manifest['sql_sha256'], 'checks': checks,
              'scope': 'Complete real catalogue; synthetic tables intentionally empty.'}
    if activity:
        result.update(scope='Complete real catalogue and explicitly fictional activity.',
                      scenario_as_of=activity['scenario_as_of'],
                      activity_sql_sha256=activity['sql_sha256'],
                      fixture_sha256=activity['fixture_sha256'], xml_sha256=activity['xml_sha256'])

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    def query(statement, database='tiago_p1'):
        statement = statement.strip().rstrip(';')
        query_path = cluster.parent/'query.sql'
        query_path.write_text("SELECT coalesce(json_agg(t), '[]'::json) FROM ("
                              + statement + ') t;\n', encoding='utf-8', newline='\n')
        return json.loads(run(client + ['-d', database, '-At', '-f', query_path]).strip())

    def counts():
        return {table: query(f'SELECT count(*) n FROM tiago_lab.{table}')[0]['n']
                for table in manifest['expected_counts']}

    def rejected_file(name, path, database, sqlstate):
        try:
            run(client + ['-d', database, '-f', path])
        except RuntimeError as error:
            check(name, sqlstate in str(error))
        else:
            raise AssertionError(name + ': unexpected success')

    try:
        run([executable('initdb'), '-D', cluster, '-U', 'dmi_p1', '--auth=trust',
             '--encoding=UTF8', '--no-locale'])
        run([executable('pg_ctl'), '-D', cluster, '-l', cluster.parent/'postgres.log',
             '-o', f'-h 127.0.0.1 -p {args.port} -c timezone=Europe/Lisbon', '-w', 'start'])
        active = query("SELECT current_setting('data_directory') AS directory", database='postgres')
        check('isolated_cluster_identity', Path(active[0]['directory']).resolve() == cluster.resolve())
        run([executable('createdb'), *connection, '-E', 'UTF8', 'tiago_p1'])
        setup = run(client + ['-d', 'tiago_p1', '-f', SQL_PATH])
        (ROOT/'results/full_catalogue_setup.txt').write_text(setup, encoding='utf-8')
        actual_counts = counts()
        for table, expected in manifest['expected_counts'].items():
            check('count_' + table, actual_counts[table] == expected)
        actual = query('SELECT establishment_id, source_id, name, address, latitude::text, '
                       'longitude::text, average_rating::text, review_count '
                       'FROM tiago_lab.establishment ORDER BY establishment_id')
        with SOURCE.open(encoding='utf-8-sig', newline='') as handle:
            source_rows = {row['restaurant_link']: row for row in csv.DictReader(handle)}
        for row in actual:
            original = source_rows[row['source_id']]
            if (row['name'], row['address']) != (original['restaurant_name'], original['address'] or None):
                raise AssertionError('Alteracao de nome/morada: ' + row['source_id'])
            for target, source in (('latitude', 'latitude'), ('longitude', 'longitude'),
                                   ('average_rating', 'avg_rating'), ('review_count', 'total_reviews_count')):
                received = None if row[target] is None else Decimal(str(row[target]))
                expected = Decimal(original[source]) if original[source].strip() else None
                if received != expected:
                    raise AssertionError('Alteracao numerica: ' + row['source_id'] + ':' + target)
        check('all_catalogue_values_match_source', len(actual) == len(source_rows)
              and {row['source_id'] for row in actual} == source_rows.keys())
        expected_labels = {(row['establishment_id'], part.strip())
                           for row in actual for part in source_rows[row['source_id']]['cuisines'].split(',')
                           if part.strip()}
        labels = query('SELECT establishment_id, label FROM tiago_lab.establishment_label')
        check('all_label_associations_match_source',
              {(row['establishment_id'], row['label']) for row in labels} == expected_labels)
        actual_ids = {row['source_id']: row['establishment_id'] for row in actual}
        check('sample_ids_preserved', all(actual_ids[source_id] == expected
              for source_id, expected in manifest['preserved_sample_ids'].items()))
        unusual_text = "D'\u00c1gua\\caf\u00e9\nsegunda linha"
        check('text_literal_round_trip', query('SELECT ' + sql_text(unusual_text) + ' AS value')[0]['value'] == unusual_text)
        rejected_file('repeat_load_refused', SQL_PATH, 'tiago_p1', '42P06')
        check('repeat_load_keeps_existing_data', counts() == actual_counts
              and query('SELECT establishment_id, source_id, name, address, latitude::text, '
                        'longitude::text, average_rating::text, review_count '
                        'FROM tiago_lab.establishment ORDER BY establishment_id') == actual
              and {(row['establishment_id'], row['label']) for row in query(
                  'SELECT establishment_id, label FROM tiago_lab.establishment_label')} == expected_labels)
        run([executable('createdb'), *connection, '-E', 'UTF8', 'tiago_p1_rejection'])
        invalid_path = cluster.parent/'invalid_load.sql'
        sql = SQL_PATH.read_text(encoding='utf-8')
        if not sql.endswith('COMMIT;\n'):
            raise AssertionError('Rever fim do SQL gerado')
        invalid_path.write_text(sql[:-len('COMMIT;\n')] +
            "INSERT INTO tiago_lab.establishment_label VALUES (2147483647, 'invalid');\nCOMMIT;\n",
            encoding='utf-8', newline='\n')
        rejected_file('invalid_load_rejected', invalid_path, 'tiago_p1_rejection', '23503')
        check('failed_load_rolls_back_schema_and_data', query(
            "SELECT count(*) n FROM pg_namespace WHERE nspname='tiago_lab'",
            database='tiago_p1_rejection') == [{'n': 0}])
        if activity:
            activity_setup = run(client + ['-d', 'tiago_p1', '-f', ACTIVITY_SQL])
            (ROOT/'results/p1_activity_setup.txt').write_text(activity_setup, encoding='utf-8')
            actual_counts = counts()
            for table, expected in activity['expected_counts'].items():
                check('activity_count_' + table, actual_counts[table] == expected)
            verify_activity(query, check)
            rejected_file('activity_repeat_load_refused', ACTIVITY_SQL, 'tiago_p1', 'P0001')
            check('activity_repeat_load_preserves_counts', counts() == actual_counts)
            check('activity_catalogue_unchanged', query(
                'SELECT establishment_id, source_id, name, address, latitude::text, '
                'longitude::text, average_rating::text, review_count '
                'FROM tiago_lab.establishment ORDER BY establishment_id') == actual
                and {(row['establishment_id'], row['label']) for row in query(
                    'SELECT establishment_id, label FROM tiago_lab.establishment_label')} == expected_labels)
            run(client + ['-d', 'tiago_p1_rejection', '-f', SQL_PATH])
            activity_text = ACTIVITY_SQL.read_text(encoding='utf-8')
            if not activity_text.endswith('COMMIT;\n'):
                raise AssertionError('Rever fim do SQL da atividade')
            invalid_activity = cluster.parent/'invalid_activity.sql'
            invalid_activity.write_text(activity_text[:-len('COMMIT;\n')] +
                "INSERT INTO tiago_lab.person VALUES (9999, 'invalid', '+351999999999', false);\nCOMMIT;\n",
                encoding='utf-8', newline='\n')
            rejected_file('activity_non_synthetic_rejected', invalid_activity, 'tiago_p1_rejection', '23514')
            check('activity_failed_load_rolls_back_all_activity',
                  all(query(f'SELECT count(*) n FROM tiago_lab.{table}', database='tiago_p1_rejection')
                      == [{'n': 0}] for table in activity['expected_counts']))
        check('source_and_sample_files_unchanged', before == {str(path): sha256(path) for path in preserved_files})
        result.update(status='passed', counts=actual_counts, checks_passed=len(checks),
                      postgresql_version=query('SELECT version() AS version')[0]['version'])
        print(f"PASS: {len(checks)} verificacoes; {actual_counts['establishment']} estabelecimentos; "
              f"{actual_counts['establishment_label']} etiquetas associadas.")
        if args.keep_open:
            print(f'Base aberta: host=127.0.0.1 porta={args.port} base=tiago_p1 utilizador=dmi_p1')
            print('Sem palavra-passe apenas nesta instancia local de treino. Schema: tiago_lab.')
            if activity:
                print('Atividade FICTICIA: 12 pessoas, 19 reservas e 28 visitas. Referencia: 21/10/2026.')
            else:
                print('Pessoas, reservas e visitas estao vazias nesta etapa.')
            print('Mantem este terminal aberto.')
            try:
                input('Carrega Enter para parar esta instancia: ')
            except (EOFError, KeyboardInterrupt):
                pass
    except Exception as error:
        result.update(status='failed', error=str(error), checks_passed=len(checks))
        raise
    finally:
        if (cluster/'postmaster.pid').exists():
            run([executable('pg_ctl'), '-D', cluster, '-m', 'fast', '-w', 'stop'])
        result['server_running_after_command'] = (cluster/'postmaster.pid').exists()
        result['finished_at'] = datetime.now().astimezone().isoformat(timespec='seconds')
        (ROOT/'results').mkdir(exist_ok=True)
        report_name = 'p1_activity_validation.json' if activity else 'full_catalogue_validation.json'
        (ROOT/'results'/report_name).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
