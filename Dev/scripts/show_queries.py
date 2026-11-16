"""Mostra no ecra os resultados das consultas SQL (B1) e XQuery (B2) de forma limpa e legivel."""
from pathlib import Path
import json
import sys
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]


def show_sql():
    path = ROOT / 'results/p1_activity_queries.json'
    if not path.exists():
        print('A executar verificacao PostgreSQL para gerar os resultados...')
        import subprocess
        subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts/check_full_catalogue.py'), '--with-activity'], check=True)
    data = json.loads(path.read_text(encoding='utf-8'))

    q1 = data['q1_sushi_rating']
    print('=' * 78)
    print(f"SQL B1 - Consulta 1 (Simples): Estabelecimentos de Sushi com rating >= 4.0")
    print(f"Total encontrado no catalogo de Lisboa: {len(q1)} estabelecimentos (a mostrar top 10)")
    print('-' * 78)
    print(f"{'ID':>5} | {'Source ID':<18} | {'Rating':>6} | {'Nome'}")
    print('-' * 78)
    for row in q1[:10]:
        print(f"{row['establishment_id']:>5} | {row['source_id']:<18} | {row['average_rating']:>6.1f} | {row['name']}")
    print(f"... (+ {len(q1) - 10} estabelecimentos)")
    print()

    q2_rows = data['q2_only_nonzero_rows']
    print('=' * 78)
    print("SQL B1 - Consulta 2 (Intermedia): Atividade em Setembro 2026 (LEFT JOIN 5.261 registos)")
    print(f"Total catalogo: {data['q2_total_establishments']} | Com visitas: {len(q2_rows)} | Sem visitas (0): {data['q2_zero_visit_establishments']}")
    print(f"Soma de eventos de visita: {data['q2_visit_events']} | Soma de presencas (party_size): {data['q2_simulated_attendances']}")
    print('-' * 78)
    print(f"{'ID':>5} | {'Source ID':<18} | {'Visitas':>7} | {'Presencas':>9} | {'Nome'}")
    print('-' * 78)
    for row in q2_rows:
        print(f"{row['establishment_id']:>5} | {row['source_id']:<18} | {row['visit_events']:>7} | {row['simulated_attendances']:>9} | {row['name']}")
    print(f"... (+ {data['q2_zero_visit_establishments']} estabelecimentos com 0 visitas e 0 presencas preservados pelo LEFT JOIN)")
    print()

    q3 = data['q3_distinct_registered_people']
    print('=' * 78)
    print("SQL B1 - Consulta 3 (Complexa): Sushi >= 4.0 com >= 2 representantes distintos em Setembro")
    print('-' * 78)
    print(f"{'Source ID':<18} | {'Pessoas Distintas':>17} | {'Presencas':>9} | {'Nome'}")
    print('-' * 78)
    for row in q3:
        print(f"{row['source_id']:<18} | {row['distinct_registered_people']:>17} | {row['simulated_attendances']:>9} | {row['name']}")
    print('=' * 78)


def show_xquery(which=None):
    out_dir = ROOT / 'results/basex_p1'
    if not (out_dir / 'validation.json').exists():
        import subprocess
        subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts/check_basex_p1.py')], check=True)

    files = sorted(out_dir.glob('*.xml'))
    if which:
        files = [f for f in files if which.lower() in f.name.lower()]
        if not files:
            print(f"Nenhum resultado XQuery correspondente a '{which}'. Opcoes: 01_museums, 02_counts, 03_cultural_interface, 04_quality, 05_contactable_places, 06_p1_quality")
            return

    parser = etree.XMLParser(remove_blank_text=True)
    for xml_file in files:
        doc = etree.parse(str(xml_file), parser)
        root = doc.getroot()
        children = list(root)
        total_children = len(children)
        print('=' * 78)
        print(f"XQuery B2: {xml_file.name}  (elemento raiz: <{root.tag}>, {total_children} elementos filhos)")
        print('-' * 78)
        if total_children > 6 and not which:
            for child in children[5:]:
                root.remove(child)
            pretty = etree.tostring(root, encoding='unicode', pretty_print=True).strip()
            print(pretty)
            print(f"  ... (+ {total_children - 5} elementos omitidos no resumo; usa 'run xquery {xml_file.stem}' para ver todos)")
        else:
            pretty = etree.tostring(root, encoding='unicode', pretty_print=True).strip()
            print(pretty)
        print()


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if mode == 'sql':
        show_sql()
    elif mode == 'xquery':
        show_xquery(arg)
    else:
        show_sql()
        print()
        show_xquery(arg)
