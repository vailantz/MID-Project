# Qualidade do catálogo PostgreSQL — preparação da P1

Análise: 2026-11-02T09:58:02+00:00

- Registos: 5261; colunas: 42.
- Registos compatíveis com as regras verificadas: 5261.
- Registos com bloqueios: 0.
- Identificadores repetidos: 0.
- Nomes repetidos: 95 grupos; não fundir por nome.
- Coordenadas ausentes: latitude 89; longitude 89.
- Avaliações ausentes: 450.
- Contagens de reviews ausentes: 6.
- Registos sem etiquetas: 811.
- Associações estabelecimento/etiqueta após separação: 12167.
- Etiquetas distintas: 105.

## Política proposta para o carregamento

- Preservar os originais; converter campos numéricos vazios em NULL, nunca em zero.
- Interpretar contagens como decimais exatos e exigir parte fracionária zero antes de converter para inteiro.
- Separar cuisines por vírgulas, retirar espaços nas extremidades e eliminar apenas repetições da mesma etiqueta no mesmo registo, como na amostra.
- Preservar os nomes e source_id; nomes iguais não são prova de duplicação.
- Não inventar coordenadas, avaliações, etiquetas ou atividade.
- Registar e resolver bloqueios antes de importar; esta análise não altera o esquema.

## Limites

Extensão das coordenadas válidas: {'latitude_min': '38.603268', 'latitude_max': '41.43351', 'longitude_min': '-9.483224', 'longitude_max': '-8.303858'}. Os registos extremos estão identificados no JSON e exigem revisão antes de usar proximidade geográfica.

A compatibilidade estrutural não prova atualidade, localização dentro do município ou identidade de locais físicos. A extensão das coordenadas consta do JSON para revisão; não é uma validação por fronteira administrativa.

O CSV é uma fonte histórica real. Pessoas, reservas e visitas serão tratadas separadamente como dados sintéticos.

As ausências por todas as colunas, os bloqueios e o SHA-256 ficam no JSON associado. O resultado não demonstra um carregamento PostgreSQL concluído.
