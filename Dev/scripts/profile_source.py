"""Analisa o CSV preservado sem alterar dados nem ligar ao PostgreSQL."""
from pathlib import Path
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
import argparse
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent/'Fontes/Tripadvisor_Kaggle/tripadvisor_lisboa.csv'
FIELDS = ('restaurant_link', 'restaurant_name', 'address', 'latitude',
          'longitude', 'avg_rating', 'total_reviews_count', 'cuisines',
          'country', 'city')


def numeric_error(raw, minimum, maximum, scale=None, integral=False):
    if not raw.strip():
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return 'not_numeric'
    if not value.is_finite():
        return 'not_finite'
    if not minimum <= value <= maximum:
        return 'out_of_range'
    if integral and value != value.to_integral_value():
        return 'not_integer'
    if scale is not None and value != value.quantize(Decimal(scale)):
        return 'would_require_rounding'
    return None


def analyse(source):
    with source.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)):
            raise ValueError('CSV com nomes de colunas repetidos')
        absent = sorted(set(FIELDS) - set(columns))
        if absent:
            raise ValueError(f'Colunas obrigatorias ausentes: {absent}')
        rows = list(reader)
    identifiers = Counter(row['restaurant_link'] for row in rows)
    names = Counter(row['restaurant_name'] for row in rows)
    duplicates = {key: count for key, count in identifiers.items() if count > 1}
    issues = []
    label_counts = Counter()
    repeated_labels = 0
    coordinate_pairs = []
    coordinate_records = []
    for record_number, row in enumerate(rows, 1):
        reasons = []
        if None in row or any(value is None for value in row.values()):
            reasons.append('malformed_csv_record')
        values = {field: row.get(field) or '' for field in FIELDS}
        for field in ('restaurant_link', 'restaurant_name'):
            if not values[field].strip():
                reasons.append(f'{field}:missing')
        if identifiers[row['restaurant_link']] > 1:
            reasons.append('restaurant_link:duplicate')
        if (values['country'], values['city']) != ('Portugal', 'Lisbon'):
            reasons.append('outside_recorded_country_city_filter')
        for field, minimum, maximum, scale, integral in (
            ('latitude', -90, 90, None, False),
            ('longitude', -180, 180, None, False),
            ('avg_rating', 0, 5, '0.1', False),
            ('total_reviews_count', 0, 2147483647, None, True),
        ):
            error = numeric_error(values[field], minimum, maximum, scale, integral)
            if error:
                reasons.append(f'{field}:{error}')
        if bool(values['latitude'].strip()) != bool(values['longitude'].strip()):
            reasons.append('unpaired_coordinates')
        if all(values[field].strip() and not numeric_error(values[field], low, high)
               for field, low, high in (('latitude', -90, 90), ('longitude', -180, 180))):
            coordinate_pairs.append((Decimal(values['latitude']), Decimal(values['longitude'])))
            coordinate_records.append({field: values[field] for field in
                                       ('restaurant_link', 'restaurant_name', 'address',
                                        'latitude', 'longitude')})
        labels = [label.strip() for label in values['cuisines'].split(',') if label.strip()]
        repeated_labels += len(labels) - len(set(labels))
        label_counts.update(set(labels))
        if reasons:
            issues.append({'record_number': record_number,
                           'source_id': values['restaurant_link'], 'reasons': reasons})
    extent = None
    if coordinate_pairs:
        extent = {
            'latitude_min': str(min(pair[0] for pair in coordinate_pairs)),
            'latitude_max': str(max(pair[0] for pair in coordinate_pairs)),
            'longitude_min': str(min(pair[1] for pair in coordinate_pairs)),
            'longitude_max': str(max(pair[1] for pair in coordinate_pairs)),
        }
    return {
        'analysed_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'source_file': str(source.resolve()),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'rows': len(rows), 'columns': len(columns),
        'missing_by_column': {field: sum(not (row.get(field) or '').strip() for row in rows)
                              for field in columns},
        'duplicate_source_ids': duplicates,
        'repeated_names_not_identity_matches': {name: count for name, count in names.items()
                                                    if name and count > 1},
        'blocking_rows': len(issues), 'compatible_rows': len(rows) - len(issues),
        'issues': issues,
        'label_associations_after_split_trim_deduplication': sum(label_counts.values()),
        'distinct_labels': len(label_counts),
        'repeated_labels_within_record': repeated_labels,
        'top_labels': label_counts.most_common(10),
        'valid_coordinate_extent': extent,
        'coordinate_extreme_records': {
            direction: chooser(coordinate_records, key=lambda row: Decimal(row[field]))
            for direction, field, chooser in (
                ('north', 'latitude', max), ('south', 'latitude', min),
                ('east', 'longitude', max), ('west', 'longitude', min))
        } if coordinate_records else {},
        'limits': [
            'Compatibility check, not an import or a verification of real-world truth.',
            'Country/city labels do not establish municipal boundaries.',
            'Names are not identifiers; matching names are not merged.',
            'Blank numeric fields become NULL; ratings are not imputed.',
            'Review counts accept integral decimal notation without float conversion.',
            'No synthetic activity is generated by this analysis.',
        ],
    }


def summary(report):
    missing = report['missing_by_column']
    lines = [
        '# Qualidade do catálogo PostgreSQL — preparação da P1', '',
        f"Análise: {report['analysed_at']}", '',
        f"- Registos: {report['rows']}; colunas: {report['columns']}.",
        f"- Registos compatíveis com as regras verificadas: {report['compatible_rows']}.",
        f"- Registos com bloqueios: {report['blocking_rows']}.",
        f"- Identificadores repetidos: {len(report['duplicate_source_ids'])}.",
        f"- Nomes repetidos: {len(report['repeated_names_not_identity_matches'])} grupos; não fundir por nome.",
        f"- Coordenadas ausentes: latitude {missing['latitude']}; longitude {missing['longitude']}.",
        f"- Avaliações ausentes: {missing['avg_rating']}.",
        f"- Contagens de reviews ausentes: {missing['total_reviews_count']}.",
        f"- Registos sem etiquetas: {missing['cuisines']}.",
        f"- Associações estabelecimento/etiqueta após separação: {report['label_associations_after_split_trim_deduplication']}.",
        f"- Etiquetas distintas: {report['distinct_labels']}.", '',
        '## Política proposta para o carregamento', '',
        '- Preservar os originais; converter campos numéricos vazios em NULL, nunca em zero.',
        '- Interpretar contagens como decimais exatos e exigir parte fracionária zero antes de converter para inteiro.',
        '- Separar cuisines por vírgulas, retirar espaços nas extremidades e eliminar apenas repetições da mesma etiqueta no mesmo registo, como na amostra.',
        '- Preservar os nomes e source_id; nomes iguais não são prova de duplicação.',
        '- Não inventar coordenadas, avaliações, etiquetas ou atividade.',
        '- Registar e resolver bloqueios antes de importar; esta análise não altera o esquema.', '',
        '## Limites', '',
        f"Extensão das coordenadas válidas: {report['valid_coordinate_extent']}. Os registos extremos estão identificados no JSON e exigem revisão antes de usar proximidade geográfica.", '',
        'A compatibilidade estrutural não prova atualidade, localização dentro do município ou identidade de locais físicos. A extensão das coordenadas consta do JSON para revisão; não é uma validação por fronteira administrativa.', '',
        'O CSV é uma fonte histórica real. Pessoas, reservas e visitas serão tratadas separadamente como dados sintéticos.', '',
        'As ausências por todas as colunas, os bloqueios e o SHA-256 ficam no JSON associado. O resultado não demonstra um carregamento PostgreSQL concluído.', '',
    ]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=ROOT/'results/source_quality.json')
    args = parser.parse_args()
    if args.output.suffix.lower() != '.json':
        parser.error('--output deve terminar em .json')
    source_directory = SOURCE.parent.resolve()
    for output in (args.output, args.output.with_suffix('.md')):
        if output.resolve() == args.csv.resolve() or output.resolve().is_relative_to(source_directory):
            parser.error('O resultado nao pode substituir a fonte nem escrever na pasta dos originais')
    report = analyse(args.csv)
    if args.csv.resolve() == SOURCE.resolve():
        provenance = json.loads((SOURCE.parent/'provenance.json').read_text(encoding='utf-8'))
        report['matches_preserved_sha256'] = report['source_sha256'] == provenance['lisbon_extract']['sha256']
        if not report['matches_preserved_sha256']:
            raise ValueError('O SHA-256 nao corresponde a proveniencia preservada')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    args.output.with_suffix('.md').write_text(summary(report), encoding='utf-8')
    print(summary(report))
    if report['blocking_rows']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
