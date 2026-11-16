# PostgreSQL — preparação da P1

Revisão iniciada em **2 de novembro de 2026**. Responsável: Tiago.

Este documento organiza o modelo existente para preparar a P1. Não altera o esquema nem constitui o relatório final. Ver `01_modelo.md` e `../postgresql/01_schema.sql`.

## 1. Objetivo e limites

Consultar estabelecimentos do catálogo selecionado de Lisboa e analisar um cenário simulado de reservas e visitas.

- Estabelecimentos e etiquetas são dados reais do catálogo histórico Tripadvisor/Kaggle, identificado no projeto como sendo de maio de 2021.
- Pessoas, reservas e visitas são fictícias; não demonstram atividade real dos estabelecimentos.
- Museus e monumentos continuam descritos no XML/BaseX; PostgreSQL guarda apenas a referência ao destino cultural da visita.
- Alojamentos e reviews ficam nas fontes do Gonçalo. Não se assume identidade comum entre pessoas fictícias e autores de reviews.
- O utilizador que consulta o sistema não é necessariamente uma `person`: esta representa o responsável fictício por uma reserva ou visita, não uma conta de acesso.

## 2. Requisitos de partida

Proposta derivada do protótipo, ainda sem validação documentada por utilizadores externos:

- **RF1:** consultar estabelecimentos pelas etiquetas e avaliação, por exemplo sushi com avaliação pelo menos 4.
- **RF2:** contar visitas e presenças simuladas num período, incluindo estabelecimentos sem visitas.
- **RF3:** distinguir reservas sem visita, visitas sem reserva e visitas associadas a uma reserva.
- **RF4:** relacionar visitas da mesma pessoa a estabelecimentos e lugares culturais sem duplicar o XML.

RF1 e RF2 correspondem às duas perguntas iniciais da fonte. RF3 justifica separar reservas de visitas. RF4 prepara a ligação à segunda fonte do Tiago; não substitui as oito consultas entre subtemas a acordar com o Gonçalo.

## 3. Entidades e relações

- **`establishment`:** um registo de estabelecimento. `establishment_id` é a chave local; `source_id` é único e preserva a identidade na origem. Nomes iguais não justificam fundir registos. A avaliação é do catálogo, não das visitas sintéticas.
- **`establishment_label`:** uma etiqueta de um estabelecimento, sem repetição do par `(establishment_id, label)`. Cada estabelecimento tem zero ou várias etiquetas; uma etiqueta pode ocorrer em vários estabelecimentos. A origem mistura culinárias e tipos de local; não impomos categoria exclusiva.
- **`person`:** uma pessoa fictícia identificada, responsável pelo grupo. O nome não é único e os acompanhantes não são identificados individualmente. Pode ter zero ou várias reservas e visitas.
- **`reservation`:** uma reserva de uma pessoa para um estabelecimento, com criação, instante marcado, dimensão do grupo e estado. A mesma pessoa pode reservar várias vezes o mesmo local. Estados: `confirmed`, `fulfilled`, `cancelled`, `no_show`.
- **`visit`:** um evento realizado no cenário, de uma pessoa, com exatamente um destino: estabelecimento SQL ou lugar cultural XML. A reserva é opcional; quando existe, pertence à mesma pessoa e estabelecimento. Cada reserva pode originar, no máximo, uma visita neste modelo.

## 4. Regras e garantias existentes

- Chaves primárias e unicidade protegem as identidades e a associação estabelecimento/etiqueta.
- Chaves estrangeiras verificam as relações locais; a chave composta da visita verifica a pessoa e o estabelecimento da reserva.
- Um `CHECK` exige exatamente um destino por visita.
- Avaliação entre 0 e 5, contagem de reviews não negativa, grupo positivo e estados controlados. Avaliação desconhecida fica `NULL`, não zero.
- Coordenadas têm intervalos válidos e presença conjunta de latitude e longitude.
- `is_synthetic` é obrigatório e verdadeiro em pessoas, reservas e visitas.
- `04_quality.sql` verifica estado cumprido, dimensão do grupo, ordem entre criação e visita e existência de visita para reservas cumpridas. Estas regras não estão todas impostas por restrições de escrita.
- `../scripts/check_demo.py` verifica os identificadores culturais no XML. Não existe chave estrangeira PostgreSQL para BaseX.

## 5. Significado das contagens e datas

- Eventos: número de registos de visita.
- Presenças acumuladas: soma de `party_size`, incluindo acompanhantes e repetições.
- Pessoas identificadas distintas: número de `person_id` diferentes, não todos os indivíduos presentes.
- Reviews: valor agregado do catálogo, não uma contagem de reservas ou visitas.

Os períodos devem ter limites explícitos no fuso de Lisboa. O cenário tem referência em **21 de outubro de 2026**, registada em `../data/provenance.json`; não se atualiza automaticamente com a data de execução.

## 6. Decisão de partida e próximo trabalho

Mantemos as cinco tabelas nesta preparação. Não acrescentamos contactos pessoais, contas, pagamentos ou outras entidades sem necessidade identificada.

A amostra tem oito estabelecimentos, 24 etiquetas, seis pessoas, sete reservas e 12 visitas. O catálogo preservado tem 5 261 registos selecionados pelos rótulos de país e cidade da origem; não se afirma que todos estejam dentro do limite administrativo de Lisboa ou ativos atualmente.

1. Inspecionar o CSV completo: ausências, identificadores repetidos, coordenadas e valores fora dos domínios do esquema.
2. Justificar o uso do catálogo completo ou de um subconjunto. Mais registos não garantem qualidade.
3. Preparar carregamento reproduzível com registo de rejeições e transformações, preservando os originais.
4. Rever o cenário sintético e preservar a amostra determinística dos testes.
5. Consolidar modelos, requisitos e resultados no relatório, com revisão do Tiago e coordenação com o colega.

Documento preparado com apoio de Codex/ChatGPT a partir dos ficheiros locais. Não implica validação por stakeholders nem aprovação académica.

## 7. Resultado da análise do catálogo — 2 de novembro de 2026

O script `../scripts/profile_source.py` analisou os 5 261 registos e 42 colunas. O SHA-256 corresponde à proveniência preservada. Não encontrou IDs repetidos nem bloqueios nas regras estruturais verificadas; isso não demonstra ainda um carregamento PostgreSQL concluído.

- 89 registos não têm coordenadas; em todos faltam latitude e longitude em conjunto.
- 450 não têm avaliação e seis não têm contagem de reviews: conservar como `NULL`.
- 811 não têm etiquetas: não criar etiquetas artificiais.
- Existem 95 grupos de nomes repetidos: preservar os IDs distintos, sem fusão automática.
- A separação das etiquetas resulta em 12 167 associações e 105 etiquetas distintas.
- As coordenadas variam de 38.603268 a 41.43351 de latitude e de -9.483224 a -8.303858 de longitude. Por exemplo, o registo `g189158-d23113230` tem latitude 41.43351, embora esteja rotulado como Lisbon. É um caso a rever, não uma coordenada a corrigir por suposição.

**Proposta seguinte:** preparar o carregamento completo para uma base de trabalho separada, conservando a amostra de testes e os IDs locais de que depende. Manter os valores originais e sinalizar dúvidas geográficas antes de consultas de proximidade; não aplicar um recorte municipal nem excluir registos silenciosamente.

O relatório está em `../results/source_quality.md`, com detalhe e registos extremos em `../results/source_quality.json`. A próxima fase é construir e testar o carregamento, não gerar mais atividade sintética antes de estabilizar o catálogo.

## 8. Carregamento completo verificado — 2 de novembro de 2026

O gerador `../scripts/prepare_full_catalogue.py` e o verificador `../scripts/check_full_catalogue.py` implementam a etapa proposta. A execução real passou 16 verificações: foram carregados 5 261 estabelecimentos e 12 167 associações a etiquetas, comparados com a fonte original. Os oito IDs locais da amostra foram preservados, sem alterar os ficheiros de origem ou os dados SQL da amostra.

O carregamento normal cria esquema e dados numa única transação. Um segundo carregamento é recusado sem substituir os dados; uma carga deliberadamente inválida noutra base de teste reverteu também a criação do esquema. A regressão independente da amostra PostgreSQL/BaseX passou as 38 verificações existentes.

Pessoas, reservas e visitas continuam vazias na versão completa. A instância usada para verificar o catálogo foi parada no fim; os ficheiros gerados e o relatório foram preservados. O [guia de execução](../postgresql/README_P1.md) explica como recriar a base e mantê-la aberta para consulta.

**Próximo passo:** preparar a atividade sintética da P1 num script separado, com cenário e data de referência explícitos. Preservar as reservas canceladas, faltas, visitas sem reserva, homónimos e referências culturais que tornam a amostra útil; não interpretar atividade fictícia como evidência sobre estabelecimentos reais.

## 9. Atividade sintética preparada — 2 de novembro de 2026

A etapa anterior está implementada no [cenário sintético](05_cenario_sintetico_p1.md): 12 pessoas, 19 reservas e 28 visitas, com referência fixa em 21/10/2026. A definição fica em JSON e o SQL gerado é separado do catálogo. O modo `--with-activity` passou 37 verificações sobre uma instância PostgreSQL nova, incluindo consultas, referências culturais, recusa de repetição e reversão de uma carga inválida.

O catálogo e os dados da amostra foram preservados. A instância de teste foi parada no final. Esta implementação não representa atividade real, não completa a integração com as fontes do Gonçalo e não fecha o relatório P1. O próximo trabalho é rever e selecionar as consultas para a entrega e consolidar a documentação dos modelos e da qualidade.
