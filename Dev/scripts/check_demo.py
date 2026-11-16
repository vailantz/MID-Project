"""Executa e verifica a iteracao de aula em PostgreSQL e BaseX locais.

Cria uma instancia PostgreSQL isolada na pasta temporaria local, apenas em loopback,
e para-a no final. Nao acede a bases de dados existentes do utilizador.
"""
from pathlib import Path
import argparse
import csv
import io
import json
import os
import shutil
import socket
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def run(args, timeout=90):
    # Ficheiros em vez de PIPE: no Windows, processos filhos do pg_ctl podem
    # herdar os pipes e impedir communicate() de terminar apos o pg_ctl sair.
    log_dir = ROOT/'.runtime/command_logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    out_fd, out_name = tempfile.mkstemp(prefix='out_', suffix='.txt', dir=log_dir)
    err_fd, err_name = tempfile.mkstemp(prefix='err_', suffix='.txt', dir=log_dir)
    import os
    with os.fdopen(out_fd, 'w', encoding='utf-8') as out, os.fdopen(err_fd, 'w', encoding='utf-8') as err:
        p = subprocess.run([str(a) for a in args], cwd=ROOT, stdout=out, stderr=err,
                           stdin=subprocess.DEVNULL, timeout=timeout, creationflags=NO_WINDOW)
    stdout = Path(out_name).read_text(encoding='utf-8', errors='replace')
    stderr = Path(err_name).read_text(encoding='utf-8', errors='replace')
    if p.returncode:
        raise RuntimeError(f'Command failed ({p.returncode}): {args[0]}\n{stderr}\n{stdout}')
    return stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pg-bin', type=Path, default=Path(r'C:\Program Files\PostgreSQL\16\bin'))
    ap.add_argument('--java', default=shutil.which('java') or 'java')
    ap.add_argument('--port', type=int, default=55439)
    ap.add_argument('--keep-open', action='store_true',
                    help='Depois da verificacao, manter o PostgreSQL acessivel ate carregar Enter')
    management = ap.add_mutually_exclusive_group()
    management.add_argument('--status', action='store_true', help='Ver se o laboratorio esta aberto')
    management.add_argument('--stop', action='store_true', help='Parar apenas o servidor de treino identificado')
    args = ap.parse_args()
    # Verificar antes de criar outra base. Nunca parar um servidor existente.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        occupied = probe.connect_ex(('127.0.0.1', args.port)) == 0
    if args.status or args.stop:
        if not occupied:
            print(f'FECHADO: nao ha um servidor acessivel na porta {args.port}.')
            return
        psql_management = [args.pg_bin/'psql.exe', '-X', '-w', '-h', '127.0.0.1',
                           '-p', str(args.port), '-U', 'dmi_lab', '-d', 'postgres',
                           '-v', 'ON_ERROR_STOP=1', '-At', '-c',
                           "SELECT json_build_object('data_directory', current_setting('data_directory'), "
                           "'is_lab', to_regclass('tiago_lab.establishment') IS NOT NULL)"]
        try:
            info = json.loads(run(psql_management, timeout=8).strip())
            active_cluster = Path(info['data_directory']).resolve()
            allowed_roots = {Path(tempfile.gettempdir()).resolve(),
                             (Path(os.environ.get('LOCALAPPDATA', tempfile.gettempdir()))/'Temp').resolve()}
            is_lab = (info['is_lab'] and active_cluster.name == 'data'
                      and active_cluster.parent.name.startswith('dmi_pg_')
                      and active_cluster.parent.parent in allowed_roots)
        except (RuntimeError, subprocess.TimeoutExpired, ValueError, KeyError, OSError):
            is_lab = False
        if not is_lab:
            print(f'A porta {args.port} esta ocupada, mas nao consegui confirmar o laboratorio DMI.')
            print('Nenhum servidor foi parado.')
            raise SystemExit(1)
        if args.status:
            print(f'ABERTO: laboratorio DMI disponivel, porta {args.port}. Prisma Studio: npm run studio')
        else:
            run([args.pg_bin/'pg_ctl.exe', '-D', active_cluster, '-m', 'fast', '-w', 'stop'])
            print('FECHADO: o servidor do laboratorio foi parado. Os ficheiros SQL foram preservados.')
        return
    if occupied:
        print(f'A porta {args.port} ja esta em uso. Pode haver um laboratorio aberto noutra janela.')
        print('Se ja arrancaste o laboratorio, abre o Prisma Studio com: npm run studio')
        print(f'Host: 127.0.0.1 | Porta: {args.port} | Base: postgres | Utilizador: dmi_lab')
        print('Nao foi criada outra base nem foi parado o servidor existente.')
        print('Para uma instancia separada, escolhe outra porta: --port 55440')
        return
    runtime = ROOT/'.runtime'; runtime.mkdir(exist_ok=True)
    # Os ficheiros ativos do PostgreSQL ficam fora do OneDrive: a sincronizacao
    # pode interferir com a criacao dos diretorios pelo initdb no Windows.
    cluster = Path(tempfile.mkdtemp(prefix='dmi_pg_'))/'data'
    cluster.mkdir()
    basex_home = runtime/'basex'; basex_home.mkdir(exist_ok=True)
    output = ROOT/'results'; output.mkdir(exist_ok=True)
    jar = ROOT/'tools/BaseX124.jar'
    if not jar.exists():
        raise FileNotFoundError('Falta tools/BaseX124.jar; consultar README.md')
    pg = lambda name: args.pg_bin/(name+'.exe')
    psql = [pg('psql'),'-X','-w','-h','127.0.0.1','-p',str(args.port),
            '-U','dmi_lab','-d','postgres','-v','ON_ERROR_STOP=1']
    java = [args.java, f'-Dorg.basex.path={basex_home}', '-cp',jar,'org.basex.BaseX']
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    def query(sql):
        sql = sql.strip().rstrip(';')
        return json.loads(run(psql+['-At','-c',
            "SELECT coalesce(json_agg(t), '[]'::json) FROM ("+sql+") t"]).strip())

    def rejected(name, sql, condition_name):
        statement = ('DO $test$ BEGIN BEGIN '+sql+'; '
          "RAISE EXCEPTION 'Invalid input was accepted'; "
          f'EXCEPTION WHEN {condition_name} THEN NULL; END; END $test$;')
        run(psql+['-c',statement])
        checks.append(name)

    started = False
    try:
        run([pg('initdb'),'-D',cluster,'-U','dmi_lab','--auth=trust','--encoding=UTF8','--no-locale'])
        run([pg('pg_ctl'),'-D',cluster,'-l',cluster.parent/'postgres.log',
             '-o',f'-h 127.0.0.1 -p {args.port} -c timezone=Europe/Lisbon','-w','start'])
        started = True
        logs = []
        for name in ['01_schema.sql','02_sample_data.sql','05_views_and_unfolding.sql']:
            logs.append(run(psql+['-f',ROOT/'postgresql'/name]))
        (output/'postgresql_setup.txt').write_text('\n'.join(logs),encoding='utf-8')
        demo = run(psql+['-f',ROOT/'postgresql/03_queries.sql'])
        (output/'sql_queries.txt').write_text(demo,encoding='utf-8')
        meta = json.loads((ROOT/'data/provenance.json').read_text(encoding='utf-8'))
        for table, count in meta['sample_counts'].items():
            check(f'count_{table}',query(f'SELECT count(*) n FROM tiago_lab.{table}')[0]['n']==count)
        sqls = (ROOT/'postgresql/03_queries.sql').read_text(encoding='utf-8')
        # Comentarios retirados apenas para separar as tres consultas de leitura.
        sqls = '\n'.join(line for line in sqls.splitlines() if not line.lstrip().startswith('--'))
        statements = [s.strip() for s in sqls.split(';') if s.strip()]
        q1,q2,q3 = [query(s) for s in statements]
        check('Q1_sushi_rating',[(r['establishment_id'],r['average_rating']) for r in q1]==[(3,4.5),(1,4.0)])
        check('Q2_month_and_zero_rows',[(r['establishment_id'],r['visit_events'],r['simulated_attendances']) for r in q2]
            ==[(1,3,7),(3,1,3),(5,1,2),(8,1,2),(4,1,1),(2,0,0),(6,0,0),(7,0,0)])
        check('Q3_distinct_people_and_attendance',q3==[{'establishment_id':1,'name':'Miss Jappa',
              'distinct_registered_people':3,'simulated_attendances':7}])
        check('homonyms_are_distinct_people',query("SELECT count(*) n FROM tiago_lab.person WHERE display_name='Ana Exemplo'")[0]['n']==2)
        check('shared_phone_distinct_people',query("SELECT count(*) n FROM tiago_lab.person WHERE contact_phone='+351910000002'")[0]['n']==2)
        check('missing_rating_stays_null',query('SELECT average_rating FROM tiago_lab.establishment WHERE establishment_id=7')[0]['average_rating'] is None)
        rejected('reject_duplicate_person_id',"INSERT INTO tiago_lab.person VALUES (1,'Outra Pessoa','+351919999999',true)",'unique_violation')
        rejected('reject_duplicate_person_natural_key',"INSERT INTO tiago_lab.person VALUES (99,'Ana Exemplo','+351910000001',true)",'unique_violation')
        rejected('reject_unknown_person',"INSERT INTO tiago_lab.visit VALUES (9001,999,1,NULL,NULL,'2026-09-01',1,true)",'foreign_key_violation')
        rejected('reject_zero_party_size',"INSERT INTO tiago_lab.visit VALUES (9001,1,1,NULL,NULL,'2026-09-01',0,true)",'check_violation')
        rejected('reject_two_visit_targets',"INSERT INTO tiago_lab.visit VALUES (9001,1,1,'museum:invalid',NULL,'2026-09-01',1,true)",'check_violation')
        rejected('reject_reservation_person_mismatch',"INSERT INTO tiago_lab.visit VALUES (9001,1,1,NULL,102,'2026-09-12',4,true)",'foreign_key_violation')
        rejected('reject_duplicate_reservation_attendance',"INSERT INTO tiago_lab.visit VALUES (9001,1,1,NULL,101,'2026-09-10',2,true)",'unique_violation')
        rejected('reject_rating_out_of_domain',"UPDATE tiago_lab.establishment SET average_rating=6 WHERE establishment_id=1",'check_violation')
        for statement in (ROOT/'postgresql/04_quality.sql').read_text(encoding='utf-8').split(';'):
            if 'SELECT' in statement:
                check('reservation_visit_consistency',query(statement)==[])
        through_view = query('SELECT DISTINCT person_id FROM tiago_lab.sushi_visitor ORDER BY person_id')
        unfolded = query("SELECT DISTINCT v.person_id FROM tiago_lab.visit v JOIN tiago_lab.establishment_label l USING(establishment_id) WHERE l.label='Sushi' ORDER BY v.person_id")
        check('view_unfolding_snapshot',through_view==unfolded==[{'person_id':1},{'person_id':2},{'person_id':3}])
        food_people = query('SELECT DISTINCT person_id FROM tiago_lab.food_visit ORDER BY person_id')
        check('containment_and_counterexample_snapshot',
              {r['person_id'] for r in through_view} < {r['person_id'] for r in food_people})

        # Exercicios preparados para a aula; usa os mesmos dados e nao altera tabelas.
        practice = ROOT/'aula/treino.sql'
        if practice.exists():
            (output/'aula_queries.txt').write_text(run(psql+['-f',practice]),encoding='utf-8')
            target = query('''SELECT e.establishment_id AS place_id,e.name
                FROM tiago_lab.establishment e WHERE e.average_rating>=4
                AND EXISTS(SELECT 1 FROM tiago_lab.establishment_label l
                           WHERE l.establishment_id=e.establishment_id AND l.label='Sushi')
                ORDER BY place_id''')
            rewritten = query('SELECT place_id,name FROM tiago_aula.sushi35 WHERE rating>=4 ORDER BY place_id')
            restricted = query('SELECT place_id,name FROM tiago_aula.sushi45 ORDER BY place_id')
            missing = query('''SELECT place_id,name FROM tiago_aula.sushi35 WHERE rating>=4
                EXCEPT SELECT place_id,name FROM tiago_aula.sushi45 ORDER BY place_id''')
            check('aula_equivalent_rewriting_snapshot',target==rewritten and len(target)==2)
            check('aula_contained_rewriting_snapshot',restricted==[{'place_id':3,'name':'Wood Sushi in a Box'}])
            check('aula_counterexample_to_equivalence',missing==[{'place_id':1,'name':'Miss Jappa'}])
            check('aula_three_cultural_visit_events',len(query('SELECT visit_id FROM tiago_lab.visit WHERE cultural_place_id IS NOT NULL'))==3)

        # Validacao XSD tem um relatorio proprio e testes negativos em copias em memoria.
        import sys
        run([sys.executable,'-X','utf8',ROOT/'scripts/validate_xml.py','--self-test'])
        schema_report = json.loads((output/'xml_schema_validation.json').read_text(encoding='utf-8'))
        check('XML_XSD_validation_and_negative_cases',schema_report['status']=='passed' and schema_report['checks_passed']==5)

        # BaseX: base persistente autonoma. A criacao e idempotente; nao apaga bases.
        xml_uri = (ROOT/'data/cultural_catalogue.xml').as_uri()
        create = "if(db:exists('tiago_culture_lab')) then () else db:create('tiago_culture_lab',doc('"+xml_uri+"'),'catalogue.xml')"
        run(java+['-q',create])
        outputs = {}
        for file in sorted((ROOT/'xml_basex').glob('*.xq')):
            value = run(java+['-i','tiago_culture_lab','-Q',file])
            (output/(file.stem+'.xml')).write_text(value,encoding='utf-8')
            outputs[file.stem] = ET.fromstring(value)
        counts = {x.attrib['name']:int(x.attrib['count']) for x in outputs['02_counts']}
        check('BaseX_counts',counts=={'museum':67,'monument':63})
        quality = outputs['04_quality']
        for field in ['duplicateIds','missingNames','unknownCategories','missingSourceReferences']:
            check('XML_'+field,quality.attrib[field]=='0')
        places = {p.attrib['id']:p for p in outputs['03_cultural_interface']}
        check('BaseX_interface_count',len(places)==130)
        cultural_refs = query('SELECT DISTINCT cultural_place_id FROM tiago_lab.cultural_visit')
        check('external_culture_references',all(r['cultural_place_id'] in places for r in cultural_refs))
        check('unknown_external_id_detected','museum:invalid' not in places)

        # Mediacao simples: SQL produz candidatos; XQuery fornece os museus.
        # O join final e feito em memoria, sem copiar o catalogo XML para PostgreSQL.
        candidates = query('''SELECT DISTINCT p.person_id, p.display_name,
            e.establishment_id, e.name AS establishment_name, cv.cultural_place_id
            FROM tiago_lab.food_visit fv
            JOIN tiago_lab.cultural_visit cv USING(person_id)
            JOIN tiago_lab.person p USING(person_id)
            JOIN tiago_lab.establishment e USING(establishment_id)
            ORDER BY p.person_id,e.establishment_id,cv.cultural_place_id''')
        integrated = []
        for row in candidates:
            place = places[row['cultural_place_id']]
            if place.attrib['category'] == 'museum':
                integrated.append({**row,'museum_name':place.findtext('name'), 'is_synthetic_activity':True})
        check('integrated_SQL_XML_query',[(r['person_id'],r['establishment_id']) for r in integrated]
              ==[(1,1),(1,3),(2,1),(2,8)])
        (output/'integrated_museum_visitors.json').write_text(json.dumps(integrated,ensure_ascii=False,indent=2),encoding='utf-8')
        sushi_places = {r['establishment_id'] for r in query("SELECT establishment_id FROM tiago_lab.establishment_label WHERE label='Sushi'")}
        integrated_sushi = [r for r in integrated if r['establishment_id'] in sushi_places]
        check('integrated_sushi_museum_query',[(r['person_id'],r['establishment_id']) for r in integrated_sushi]
              ==[(1,1),(1,3),(2,1)])
        check('integrated_query_containment_counterexample',
              {(r['person_id'],r['establishment_id']) for r in integrated_sushi}
              < {(r['person_id'],r['establishment_id']) for r in integrated})
        (output/'integrated_sushi_museum.json').write_text(json.dumps(integrated_sushi,ensure_ascii=False,indent=2),encoding='utf-8')
        normal = query("SELECT sum(party_size) n FROM tiago_lab.visit WHERE establishment_id=1 AND visited_at >= '2026-09-01 00:00+01' AND visited_at < '2026-10-01 00:00+01'")[0]['n']
        inflated = query("SELECT sum(v.party_size) n FROM tiago_lab.visit v JOIN tiago_lab.establishment_label l USING(establishment_id) WHERE establishment_id=1 AND visited_at >= '2026-09-01 00:00+01' AND visited_at < '2026-10-01 00:00+01'")[0]['n']
        check('fanout_counterexample',normal==7 and inflated==21)
        versions={'postgresql':run([pg('psql'),'--version']).strip(),
                  'BaseX':'12.4 (BaseX124.jar)', 'Java':args.java}
        report={'status':'passed','date':'2026-10-21','versions':versions,
                'checks_passed':len(checks),'checks':checks,'source_counts':meta['sample_counts'],
                'culture_counts':counts,'integrated_rows':len(integrated),
                'counterexample':{'correct_attendance':normal,'incorrect_join_total':inflated},
                'limits':['Educational subset, not complete P1 or P2',
                          'All activity simulated; historical real catalogue',
                          'Tests on one snapshot do not prove general query equivalence',
                          'No integration with colleague sources executed yet']}
        (output/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
        if args.keep_open:
            print('\nLaboratorio aberto. Manter este terminal aberto enquanto trabalhas.')
            print(f'pgAdmin/psql: host=127.0.0.1 port={args.port} database=postgres user=dmi_lab')
            print('Prisma Studio: abre outro CMD nesta pasta e executa npm run studio (porta PostgreSQL 55439).')
            print('Esta instancia local de treino nao exige palavra-passe. Os esquemas sao tiago_lab e tiago_aula.')
            print('BaseX: .\\scripts\\basex.ps1 -i tiago_culture_lab -Q .\\xml_basex\\02_counts.xq')
            try:
                input('Carrega Enter neste terminal apenas quando quiseres parar o PostgreSQL: ')
            except (EOFError,KeyboardInterrupt):
                pass
    finally:
        if started and (cluster/'postmaster.pid').exists():
            run([pg('pg_ctl'),'-D',cluster,'-m','fast','-w','stop'])


if __name__ == '__main__':
    main()
