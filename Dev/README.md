# Primeira iteração de trabalho — Tiago, 21 de outubro de 2026

Esta pasta desenvolve a parte de **oferta local, reservas e visitas** da proposta aceite. É uma primeira base para estudar e continuar na aula: uma fonte PostgreSQL pequena e uma fonte cultural XML consultada em BaseX. O SQL antigo do ZIP da proposta não foi usado na construção desta versão. A comparação fica para depois.

## Começar por aqui

**Revisão para a próxima aula (02/11/2026):** ver [requisitos consolidados](models/07_requisitos_p1.md), [auditoria do enunciado e da matéria](models/08_auditoria_materia_p1.md) e [esboço de entidades, ligações e casos de uso](models/09_esboco_aula.md). O esboço separa implementação e propostas; contactos e estadias sintéticos ainda não foram acrescentados. Os roteiros de outubro descrevem a amostra histórica, não todo o estado P1 atual.

**Preparação da P1:** começar pela [revisão do modelo PostgreSQL](models/04_postgresql_p1.md), iniciada em 02/11/2026. Organiza requisitos, tabelas, regras e decisões pendentes antes do carregamento para a entrega. A amostra de aula continua preservada.

**Qualidade do catálogo completo:** executar `python scripts/profile_source.py` nesta pasta. O script apenas lê o CSV preservado, confirma o SHA-256 e guarda o [resumo](results/source_quality.md) e o [detalhe JSON](results/source_quality.json). Não importa dados nem altera os originais. Registos com bloqueios fazem o comando terminar com código 1, depois de guardar o relatório; falhas de estrutura ou de integridade da fonte interrompem a execução sem gerar um novo relatório.

**Carregamento completo da P1:** seguir o [guia PostgreSQL](postgresql/README_P1.md). `python -X utf8 scripts/check_full_catalogue.py` prepara, carrega e verifica os 5 261 estabelecimentos numa instância nova, separada da amostra. Para consultar ao vivo, acrescentar `--keep-open` e executar `npm run studio:p1` num segundo terminal. Pessoas, reservas e visitas ainda ficam vazias nesta versão completa.

**Cenário sintético da P1:** usar `python -X utf8 scripts/check_full_catalogue.py --with-activity --keep-open` para abrir o catálogo com 12 pessoas, 19 reservas e 28 visitas fictícias; depois executar `npm run studio:p1` noutro terminal. O [guia do cenário](models/05_cenario_sintetico_p1.md) explica os casos, a referência fixa em 21/10/2026 e os resultados esperados. Sem `--with-activity`, o comando anterior continua a carregar apenas o catálogo.

**XML/BaseX da P1:** executar `python -X utf8 scripts/check_basex_p1.py`. Prepara e verifica os 67 museus e 63 monumentos na base `tiago_culture_p1`, num estado separado da aula e sem iniciar PostgreSQL. O [guia BaseX](xml_basex/README_P1.md) contém os comandos de consulta; o [modelo cultural](models/06_xml_basex_p1.md) organiza as decisões para o relatório. A preparação passou 36 verificações e preservou o XML aceite.

**Interface escolhida: Prisma Studio.** No CMD, nesta pasta, mantém a base aberta com `python scripts\check_demo.py --keep-open`. Num segundo CMD, também nesta pasta, executa `npm run studio` e abre http://localhost:5555. Seleciona **Schema → tiago_lab** e depois uma tabela, por exemplo `establishment`, `person`, `reservation` ou `visit`. A instalação local já foi feita; basta repetir o arranque. Fecha o Studio com Ctrl+C no segundo CMD. Para parar o PostgreSQL, carrega Enter no primeiro CMD ou usa `python scripts\check_demo.py --stop` noutro terminal. Esta amostra é recriada em cada arranque da base; guarda o trabalho em SQL.

O Studio liga-se diretamente ao PostgreSQL existente. Não foram introduzidas migrações ou alterações ao modelo por esta configuração. `package.json` e `package-lock.json` registam a ferramenta; `node_modules` contém a instalação local. Para reinstalar as dependências numa cópia desta pasta, usar `npm ci`.

**Para a aula de hoje, abre [aula/README.md](aula/README.md).** Para mostrar o ponto de situação ao Gonçalo, usa [o roteiro curto](aula/MOSTRAR_AO_GONCALO.md).

1. Ler [o modelo e as decisões](models/01_modelo.md). Começar pelas duas perguntas de utilização, depois seguir as relações entre as tabelas.
2. Abrir [o esquema SQL](postgresql/01_schema.sql) e [os dados de exemplo](postgresql/02_sample_data.sql). Os comentários explicam o significado de cada tabela.
3. Antes de executar [as três consultas SQL](postgresql/03_queries.sql), prever os resultados descritos nos comentários. Comparar com [os resultados guardados](results/sql_queries.txt).
4. Ver [as contagens XML](xml_basex/02_counts.xq) e [o resultado integrado](results/integrated_museum_visitors.json).
5. Trabalhar a [preparação da aula de hoje](models/02_materia_recente.md): a comparação entre teoria e práticas está na secção 8; as três situações de treino e a revisão de 25 minutos estão nas secções 10–11.

## O que existe nesta iteração

| Fonte | Dados reais usados | Dados sintéticos | Tecnologia |
|---|---|---|---|
| B1 — estabelecimentos | 8 registos escolhidos diretamente no CSV original do arquivo Kaggle; 24 etiquetas preservadas | 6 pessoas, 7 reservas e 12 visitas | PostgreSQL 16; SQL |
| B2 — cultura | Cópia inalterada do XML aceite: 67 registos de museus e 63 de monumentos | Nenhum evento inserido no catálogo XML | BaseX 12.4; XPath/XQuery |

Os 8 estabelecimentos são uma **amostra didática**, não o catálogo final dos 5 261 registos de Lisboa. Incluem sushi, café e etiquetas Bar/Pub, uma avaliação em falta e locais sem visitas no mês. A seleção é fixa e está registada em [data/provenance.json](data/provenance.json).

Os nomes, avaliações e coordenadas dos estabelecimentos são do catálogo histórico de maio de 2021. As pessoas e atividades são inteiramente fictícias. A associação de um estabelecimento a uma visita em 2026 é uma hipótese do cenário, sem verificação da sua atividade real nessa data. Os 130 elementos XML são registos de catálogo, sem afirmar que todos correspondem a locais físicos distintos.

O PDF aceite continua a ser a referência de âmbito e está em `Projeto/Docs/project_proposal.pdf`. As fontes do Gonçalo estão em `Projeto/Fontes/InsideAirbnb`. A organização das pastas não alterou o conteúdo destes ficheiros. A análise desta iteração não é uma revisão da proposta.

## Executar a demonstração completa

Requisitos: Python 3, PostgreSQL 16 instalado e Java 17 ou superior. A demonstração usa a biblioteca standard e `lxml` para a validação XSD. O Python incluído neste ambiente já tem essa dependência. O pacote oficial portátil do BaseX está em `tools/BaseX124.jar`; não foi feita uma instalação global.

Abrir um terminal **nesta pasta** e executar:

```powershell
python .\scripts\check_demo.py
```

Para trabalhar ao vivo em pgAdmin/psql, faz duplo clique em **[ABRIR_LAB.cmd](ABRIR_LAB.cmd)**. Não é preciso abrir o PowerShell nem executar como administrador. Espera por “Laboratorio aberto” e mantém a janela aberta. Carrega Enter nessa janela quando quiseres parar. As instruções de ligação estão no guia da aula.

O programa cria uma instância PostgreSQL isolada na pasta temporária local do Windows, fora do OneDrive, acessível apenas no próprio computador, na porta 55439, executa a demonstração e para essa instância no fim. Usa autenticação local de confiança apenas nesta instância de teste: não é uma configuração para um serviço partilhado. Não tenta aceder ao teu PostgreSQL habitual. Se a porta estiver ocupada, usar `--port 55440`.

Também cria a base BaseX `tiago_culture_lab` na configuração local de `.runtime/basex`. Os resultados ficam em `results`. O relatório [validation.json](results/validation.json) regista o que foi realmente verificado e as versões utilizadas.

Se o PostgreSQL estiver noutro local:

```powershell
python .\scripts\check_demo.py --pg-bin 'C:\Program Files\PostgreSQL\16\bin'
```

Nesta máquina, o Python usado na verificação foi:

```powershell
& 'C:\Users\tiago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 .\scripts\check_demo.py
```

### Trabalhar manualmente em PostgreSQL

No pgAdmin, criar uma **nova base de dados de trabalho** e executar, por ordem:

1. `postgresql/01_schema.sql` — cria o esquema `tiago_lab` e cinco tabelas.
2. `postgresql/02_sample_data.sql` — carrega os registos.
3. `postgresql/03_queries.sql` — filtra, agrega e relaciona informação.
4. `postgresql/04_quality.sql` — verifica a coerência entre reservas e visitas.
5. `postgresql/05_views_and_unfolding.sql` — cria vistas e compara uma consulta com a sua expansão.

Os scripts de criação não apagam um esquema existente e não devem ser executados duas vezes sobre as mesmas tabelas. Para uma nova tentativa manual, escolher outra base de dados. O programa de demonstração faz sempre uma instância de teste nova.

### Trabalhar manualmente em BaseX

Para executar uma consulta sobre o ficheiro XML:

```powershell
.\scripts\basex.ps1 -i .\data\cultural_catalogue.xml -Q .\xml_basex\02_counts.xq
```

Depois da demonstração, também podes consultar a base persistente:

```powershell
.\scripts\basex.ps1 -i tiago_culture_lab -Q .\xml_basex\01_museums.xq
```

Se usares a interface gráfica do BaseX, cria/abre uma base a partir de `data/cultural_catalogue.xml`, abre um ficheiro `.xq` no editor e executa-o com essa base selecionada. O primeiro comando acima consulta o ficheiro; o segundo consulta a base carregada. O conteúdo deve ser o mesmo.

O script reutiliza a base cultural quando ela já existe. Se alterares o XML de trabalho mais tarde, terás de atualizar/reimportar essa base de forma explícita; não se deve assumir que ela acompanha automaticamente alterações ao ficheiro.

## O que esta preparação cobre — e o que fica para as próximas iterações

Há um modelo inicial, criação e população SQL, consultas locais SQL/XQuery, validação XSD da estrutura cultural comum, testes de integridade, proveniência, casos de duplicação e uma pequena execução que cruza **as tuas duas fontes**. Os resultados culturais são obtidos em BaseX e ligados aos resultados SQL em memória. Não foram copiados para uma tabela cultural PostgreSQL.

Isto ainda não é a entrega P1 nem a integração P2 completa. Falta acordar com o Gonçalo o esquema global e as oito perguntas entre subtemas, integrar as fontes dele, alargar os dados e preparar os restantes modelos, relatório e demonstração pedidos no enunciado. As três consultas SQL aqui são exercícios de preparação; não substituem a distribuição obrigatória das doze consultas do grupo.

Para a próxima sessão, as decisões prioritárias são:

- Confirmar o significado de “pessoa”: nesta iteração é o visitante identificado/responsável pela reserva, não todos os acompanhantes.
- Rever o modelo antes de o alargar aos 5 261 estabelecimentos. Não precisamos de telefones ou emails para responder às duas perguntas iniciais.
- Afinar as etiquetas: a origem mistura `Sushi`, `Japanese`, `Cafe`, `Bar`, `Pub` na coluna `cuisines`. Preservámos essa informação, sem inventar uma classificação exclusiva.
- Acrescentar campos como funcionalidades e horários quando uma pergunta concreta precisar deles. O ficheiro com a amostra original conserva esses valores.
- Definir com o colega a interface de alojamentos e a convenção geográfica. Não assumir identidades comuns entre pessoas sintéticas e autores de reviews reais.

## Proveniência e materiais

O arquivo original completo e o CSV filtrado com os **5 261 registos de Lisboa** estão guardados em `Projeto/Fontes/Tripadvisor_Kaggle`. Consultar [a descrição dessa fonte](../Fontes/Tripadvisor_Kaggle/README.md). Estes ficheiros são o catálogo real; as pessoas, reservas e visitas da nossa implementação são dados sintéticos separados. A fonte XML preservada está em `Projeto/Fontes/Camara_Municipal/79922_2.xml`; `data/cultural_catalogue.xml` é a cópia de trabalho.

O extrato original da amostra está em `data/tripadvisor_sample_original.json`: foi extraído do CSV, não do SQL antigo. Esse JSON é um ficheiro de apoio à reprodução; **a fonte B1 implementada é a base relacional**, não uma terceira fonte.

`scripts/prepare_sample.py` documenta a seleção e cada evento fictício. Por omissão, lê os dados preservados em `Projeto/Fontes`. Para regenerar a amostra a partir de outros caminhos, usar `--source-zip` e `--culture-xml`. O XML aprovado é copiado sem transformação. Os resumos SHA-256 ficam no ficheiro de proveniência.

Os diretórios de bases de teste `.runtime` são recriáveis pelo programa de demonstração. Foram eliminados na limpeza de 21/10 para poupar espaço; os scripts, dados e resultados verificados foram preservados. O ZIP redundante desta iteração também foi eliminado. A pasta presente é a versão de trabalho.

As referências da disciplina, com páginas relevantes, estão em [models/03_referencias.md](models/03_referencias.md). Documentação técnica consultada em 21/10/2026:

- [BaseX: requisitos e distribuições](https://docs.basex.org/main/Startup).
- [BaseX: opções de execução](https://docs.basex.org/main/Command-Line_Options).
- [BaseX: configuração local](https://docs.basex.org/main/Configuration).
- [Download oficial](https://basex.org/download/), pacote `https://files.basex.org/releases/12.4/BaseX124.jar`.

## Declaração de apoio por IA

Codex/ChatGPT auxiliou na leitura dos materiais, desenho desta iteração, preparação dos scripts, cenário sintético, documentação e execução das verificações. Tiago deve rever as decisões e compreender as consultas antes de as apresentar. O registo de execução demonstra verificações técnicas, não substitui a validação académica pelo aluno ou pela professora.
