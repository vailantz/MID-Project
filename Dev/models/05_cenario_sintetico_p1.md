# Cenário sintético PostgreSQL — P1

Preparado em **2 de novembro de 2026**, com referência temporal fixa em **21 de outubro de 2026, às 23:59:59 de Lisboa**. Uma reserva futura neste documento é futura relativamente a essa referência, não à data em que o programa é executado.

## Objetivo e âmbito

Testar o modelo e as consultas com atividade pequena, explícita e reproduzível. O catálogo tem 5 261 registos reais históricos; as 12 pessoas, 19 reservas e 28 visitas deste cenário são inteiramente fictícias. Não se pretende reproduzir procura real nem preencher artificialmente todos os estabelecimentos.

A definição editável está em `../data/synthetic_activity.json`. As listas `columns` declaram a ordem dos campos de cada linha. Os estabelecimentos são referenciados pelo `source_id` original, não pelo nome ou por um ID local presumido. O gerador resolve essa referência ao criar o SQL.

O cenário preserva os seis participantes, sete reservas e 12 visitas da amostra, acrescentando seis participantes, 12 reservas e 16 visitas. Os dados SQL e os testes da amostra anterior não foram alterados.

## Casos incluídos e respetiva justificação

- **Homónimos:** as pessoas 1 e 3 chamam-se Ana Exemplo e continuam distintas.
- **Ausência de atividade:** Eva Exemplo não tem reservas ou visitas. Também existem estabelecimentos sem eventos no período, para verificar os zeros do `LEFT JOIN`.
- **Reservas repetidas:** Filipe Exemplo reserva duas vezes Miyagi Sushi; a combinação pessoa/estabelecimento não pode ser a chave da reserva.
- **Estados distintos:** 12 reservas cumpridas, duas canceladas, duas faltas e três confirmadas para depois da referência do cenário. Apenas as cumpridas têm visita associada.
- **Visitas sem reserva:** nove visitas a estabelecimentos não resultam de reservas. As sete visitas culturais também não têm reserva neste modelo.
- **Destino exclusivo:** 21 visitas têm destino num estabelecimento e sete num lugar cultural; nenhuma tem dois destinos.
- **Acompanhantes:** a dimensão do grupo inclui a pessoa responsável, mas não identifica individualmente os acompanhantes. Presenças não equivalem a pessoas distintas.
- **Limite mensal:** a visita 1020 ocorre em 30/09/2026 às 23:59 e pertence a setembro; a visita 1012, em 01/10/2026 às 00:00, fica fora desse mês.
- **Etiquetas ausentes:** Cachorraria Nacional recebe atividade sem que sejam inventadas etiquetas para o registo original.

Os quatro estabelecimentos acrescentados à atividade são Miyagi Sushi (`g189158-d10466969`), Pau de Canela (`g189158-d10044466`), RendezVous (`g189158-d10025218`) e Cachorraria Nacional (`g189158-d10006576`). A escolha é didática, não aleatória nem representativa. A atividade continua hipotética: não se verificam funcionamento em 2026, horários de abertura, capacidade ou disponibilidade de reservas. O evento às 23:59 é deliberadamente um teste de fronteira temporal.

## Geração e garantias

Em `Projeto/Dev`, executar `python -X utf8 scripts/prepare_synthetic_activity.py` valida o JSON e gera `postgresql/generated/synthetic_activity.sql` e o respetivo manifesto. Não inicia PostgreSQL nem altera o XML. Também regenera o SQL do catálogo para que o manifesto da atividade identifique exatamente a versão de que depende.

O gerador rejeita IDs repetidos, pessoas ou destinos desconhecidos, grupos inválidos, estados inesperados, instantes sem offset, visitas posteriores à referência e incoerências entre reservas e visitas. Cada reserva cumprida tem exatamente uma visita; as restantes não têm nenhuma.

O XML de trabalho e o original preservado têm de corresponder ao SHA-256 registado. Os IDs culturais são verificados no XML antes de gerar o SQL e novamente nos testes da base carregada. Isto não cria uma chave estrangeira PostgreSQL para BaseX nem prova uma integração virtual completa.

O SQL da atividade tem transação própria e exige o catálogo completo e tabelas de atividade vazias. Não apaga dados, não atualiza estados nem volta a inserir atividade sobre uma versão já povoada. Se a carga da atividade falhar, essa transação reverte; o catálogo previamente carregado permanece.

## Consultas de verificação

O ficheiro `../postgresql/06_p1_activity_queries.sql` contém três consultas candidatas para testar dificuldades diferentes. A escolha das duas consultas individuais finais e das oito consultas entre subtemas continua a exigir coordenação com o Gonçalo.

1. **Simples:** estabelecimentos com etiqueta Sushi e avaliação pelo menos 4. Consulta o catálogo real, não apenas os locais com atividade.
2. **Intermédia:** eventos e presenças simuladas por estabelecimento em setembro de 2026, incluindo os zeros. Resultado: 5 261 linhas, 19 eventos em nove estabelecimentos, 42 presenças acumuladas e 5 252 estabelecimentos sem eventos nesse mês do cenário.
3. **Complexa neste exercício:** locais de sushi com avaliação pelo menos 4 visitados em setembro por pelo menos duas pessoas responsáveis distintas. Resultado: Miss Jappa, três pessoas e sete presenças; Miyagi Sushi, três pessoas e dez presenças.

Os 28 eventos de todos os destinos somam 61 presenças acumuladas no cenário inteiro. Isto não significa 61 indivíduos diferentes. Os zeros também não demonstram ausência de procura real.

## Execução verificada

Executar `python -X utf8 scripts/check_full_catalogue.py --with-activity` cria uma instância nova e isolada, carrega primeiro o catálogo e depois a atividade, executa os testes e para o servidor no fim. Para consultar no Studio, acrescentar `--keep-open` e executar `npm run studio:p1` noutro terminal.

Na execução de 02/11/2026 passaram 37 verificações, incluindo comparação de todos os registos da atividade com o JSON, regras de qualidade, IDs externos, limites mensais, consultas, recusa de carga repetida e reversão integral de uma carga com dados não sintéticos. Foram também testadas e rejeitadas 21 alterações inválidas ao cenário e confirmada a geração determinística do SQL.

Resultados em `../results/p1_activity_validation.json`, `../results/p1_activity_setup.txt` e `../results/p1_activity_queries.json`. O último ficheiro guarda a primeira e a terceira consultas e um resumo explícito da segunda: linhas com visitas mais contagem de linhas zero, não as 5 261 linhas completas. O SQL permite reproduzir o resultado completo.

Preparado com apoio de Codex/ChatGPT. Tiago deve rever e compreender os casos e as consultas antes de os apresentar; esta verificação técnica não substitui a validação académica ou por stakeholders.
