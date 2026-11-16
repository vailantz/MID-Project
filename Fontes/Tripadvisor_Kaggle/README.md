# Fonte original dos estabelecimentos

O arquivo já estava no computador desde **14/10/2026**. Em **21/10/2026** foi copiado da pasta temporária de pesquisa para esta pasta do projeto. Não foi necessário voltar a descarregar.

## Origem

- **Dataset:** [TripAdvisor European restaurants, publicado por Stefano Leone no Kaggle](https://www.kaggle.com/datasets/stefanoleone992/tripadvisor-european-restaurants).
- Tripadvisor é a plataforma de onde provêm as informações dos estabelecimentos; Kaggle é o local de publicação/distribuição do dataset que usamos.
- A proposta regista recolha em maio de 2021 e licença CC0 declarada pelo publicador. É um catálogo histórico, não uma ligação em tempo real ao Tripadvisor.
- O formato descarregado é um **CSV dentro de um ZIP**. PostgreSQL é a tecnologia em que implementamos a nossa fonte de trabalho a partir destes dados.

## Ficheiros

| Ficheiro | Conteúdo |
|---|---|
| `tripadvisor_european_restaurants.zip` | Original completo: 1,083,397 registos e 42 colunas; cópia verificada por SHA-256 |
| `tripadvisor_lisboa.csv` | Os 5,261 registos com `country = Portugal` e `city = Lisbon`; todas as colunas e valores originais preservados |
| `provenance.json` | Origem, filtro, contagens, tamanhos e hashes para reprodução |

Não é necessário extrair agora o CSV europeu completo, que ocupa cerca de 680 MB. Ele já está guardado dentro do ZIP original. O CSV de Lisboa está pronto para inspeção e futura importação.

## Dados reais e dados sintéticos

Estes ficheiros contêm o catálogo real publicado: nomes, moradas, coordenadas, etiquetas/culinárias, avaliações agregadas, contagens de reviews e outros atributos, quando disponíveis.

**Não contêm as pessoas, reservas ou visitas individuais que queremos modelar.** Na nossa parte do projeto, essas entidades e eventos serão inteiramente sintéticos e ficarão identificados como tal nas tabelas PostgreSQL. Não são retirados de contas de utilizadores Tripadvisor e não correspondem a pessoas reais.

A contagem de reviews de um estabelecimento não é uma contagem de visitas. Uma avaliação agregada não identifica quem a deu. Os dados sintéticos simulam atividade para testar o modelo e as consultas; não demonstram frequência real dos estabelecimentos.

## Relação com o exercício inicial

`Projeto/Dev` usa apenas oito destes estabelecimentos numa primeira amostra didática. Os 5,261 registos completos de Lisboa estão aqui guardados; a amostra de oito não substitui a fonte.

O script `Projeto/Dev/scripts/organise_original_source.py` documenta a extração. A seleção geográfica usa os rótulos da origem, sem afirmar um recorte por fronteira municipal nem que todos os estabelecimentos continuam abertos.
