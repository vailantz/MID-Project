"""Preserva o arquivo Kaggle local e extrai Lisboa sem alterar os valores originais."""
from pathlib import Path
import csv
import hashlib
import io
import json
import shutil
import zipfile

MID = Path(__file__).resolve().parents[3]
DEST = MID/'Projeto/Fontes/Tripadvisor_Kaggle'
ORIGINAL = DEST/'tripadvisor_european_restaurants.zip'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    archive = DEST/ORIGINAL.name
    if not archive.exists():
        shutil.copy2(ORIGINAL, archive)
    original_hash = digest(ORIGINAL)
    assert digest(archive) == original_hash, 'Original archive copy differs'
    csv_path = DEST/'tripadvisor_lisboa.csv'
    if csv_path.exists():
        raise FileExistsError('Lisbon CSV already exists; inspect before replacing it')
    total = 0
    lisbon = 0
    source_ids = set()
    duplicate_ids = []
    with zipfile.ZipFile(archive) as z:
        members = [m for m in z.infolist() if m.filename.lower().endswith('.csv')]
        assert len(members) == 1
        member = members[0]
        # Reading the full stream also verifies the member CRC when EOF is reached.
        with z.open(member) as raw, csv_path.open('w', encoding='utf-8-sig', newline='') as out:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig', newline=''))
            fields = reader.fieldnames
            writer = csv.DictWriter(out, fieldnames=fields)
            writer.writeheader()
            for row in reader:
                total += 1
                if row['country'] == 'Portugal' and row['city'] == 'Lisbon':
                    writer.writerow(row)
                    lisbon += 1
                    sid = row['restaurant_link']
                    if sid in source_ids:
                        duplicate_ids.append(sid)
                    source_ids.add(sid)
    assert total == 1083397 and lisbon == 5261, (total, lisbon)
    with csv_path.open(encoding='utf-8-sig', newline='') as f:
        extracted_count = sum(1 for _ in csv.DictReader(f))
    assert extracted_count == lisbon
    manifest = {
        'organised_on':'2026-10-21',
        'original_download_date_recorded':'2026-10-14',
        'downloaded_again':False,
        'publisher':'Stefano Leone on Kaggle',
        'dataset':'TripAdvisor European restaurants',
        'catalogue_url':'https://www.kaggle.com/datasets/stefanoleone992/tripadvisor-european-restaurants',
        'distribution_url':'https://www.kaggle.com/api/v1/datasets/download/stefanoleone992/tripadvisor-european-restaurants',
        'origin_description':'Tripadvisor establishment catalogue published as a dataset on Kaggle; not a live Tripadvisor API',
        'snapshot_recorded_in_proposal':'May 2021',
        'licence_recorded_in_proposal':'CC0 according to publisher',
        'original_archive':{'file':archive.name,'bytes':archive.stat().st_size,'sha256':original_hash,
                            'csv_member':member.filename,'uncompressed_csv_bytes':member.file_size,
                            'rows':total,'columns':len(fields),'crc_verified_by_full_read':True},
        'lisbon_extract':{'file':csv_path.name,'bytes':csv_path.stat().st_size,'sha256':digest(csv_path),
                          'rows':lisbon,'columns':len(fields),'encoding':'UTF-8 with BOM',
                          'selection':"country = 'Portugal' AND city = 'Lisbon'",
                          'transformations':'Row selection only; original columns and field values retained. CSV quoting reserialized.',
                          'duplicate_restaurant_link_count':len(duplicate_ids)},
        'synthetic_data_in_these_files':False,
        'people_and_activity':'No generated people/reservations/visits in these files; those are separate synthetic project data.',
    }
    (DEST/'provenance.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (DEST/'README.md').write_text(f'''# Fonte original dos estabelecimentos

O arquivo já estava no computador desde **14/10/2026**. Em **21/10/2026** foi copiado da pasta temporária de pesquisa para esta pasta do projeto. Não foi necessário voltar a descarregar.

## Origem

- **Dataset:** [TripAdvisor European restaurants, publicado por Stefano Leone no Kaggle](https://www.kaggle.com/datasets/stefanoleone992/tripadvisor-european-restaurants).
- Tripadvisor é a plataforma de onde provêm as informações dos estabelecimentos; Kaggle é o local de publicação/distribuição do dataset que usamos.
- A proposta regista recolha em maio de 2021 e licença CC0 declarada pelo publicador. É um catálogo histórico, não uma ligação em tempo real ao Tripadvisor.
- O formato descarregado é um **CSV dentro de um ZIP**. PostgreSQL é a tecnologia em que implementamos a nossa fonte de trabalho a partir destes dados.

## Ficheiros

| Ficheiro | Conteúdo |
|---|---|
| `tripadvisor_european_restaurants.zip` | Original completo: {total:,} registos e {len(fields)} colunas; cópia verificada por SHA-256 |
| `tripadvisor_lisboa.csv` | Os {lisbon:,} registos com `country = Portugal` e `city = Lisbon`; todas as colunas e valores originais preservados |
| `provenance.json` | Origem, filtro, contagens, tamanhos e hashes para reprodução |

Não é necessário extrair agora o CSV europeu completo, que ocupa cerca de 680 MB. Ele já está guardado dentro do ZIP original. O CSV de Lisboa está pronto para inspeção e futura importação.

## Dados reais e dados sintéticos

Estes ficheiros contêm o catálogo real publicado: nomes, moradas, coordenadas, etiquetas/culinárias, avaliações agregadas, contagens de reviews e outros atributos, quando disponíveis.

**Não contêm as pessoas, reservas ou visitas individuais que queremos modelar.** Na nossa parte do projeto, essas entidades e eventos serão inteiramente sintéticos e ficarão identificados como tal nas tabelas PostgreSQL. Não são retirados de contas de utilizadores Tripadvisor e não correspondem a pessoas reais.

A contagem de reviews de um estabelecimento não é uma contagem de visitas. Uma avaliação agregada não identifica quem a deu. Os dados sintéticos simulam atividade para testar o modelo e as consultas; não demonstram frequência real dos estabelecimentos.

## Relação com o exercício inicial

`Projeto/Dev` usa apenas oito destes estabelecimentos numa primeira amostra didática. Os {lisbon:,} registos completos de Lisboa estão aqui guardados; a amostra de oito não substitui a fonte.

O script `Projeto/Dev/scripts/organise_original_source.py` documenta a extração. A seleção geográfica usa os rótulos da origem, sem afirmar um recorte por fronteira municipal nem que todos os estabelecimentos continuam abertos.
''', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
