# Catálogo completo PostgreSQL — P1

Preparação iniciada em 2 de novembro de 2026. Por omissão carrega apenas o catálogo real; a opção `--with-activity` acrescenta o cenário fictício. Ainda não é a entrega P1 completa.

Na execução de 02/11/2026, passaram as 16 verificações do catálogo completo e as 38 verificações da regressão independente da amostra PostgreSQL/BaseX. A instância do catálogo foi parada no fim. Consultar o relatório de cada nova execução, em vez de assumir que estes resultados históricos se repetem.

## O que se carrega

- 5 261 estabelecimentos da seleção preservada de Lisboa e 12 167 associações a etiquetas.
- O esquema existente `tiago_lab`, com as mesmas cinco tabelas da amostra.
- Sem `--with-activity`, pessoas, reservas e visitas ficam vazias. Com essa opção, carregam-se 12 pessoas, 19 reservas e 28 visitas fictícias através de um SQL separado.
- Coordenadas e outros valores históricos são preservados, incluindo casos geográficos duvidosos. Não se inventam valores em falta nem se aplica um recorte municipal.

O catálogo completo usa uma instância diferente da amostra: base `tiago_p1`, utilizador `dmi_p1`, porta 55441. A amostra continua na porta 55439, com os comandos anteriores.

## 1. Gerar os ficheiros sem iniciar PostgreSQL

Num terminal em `Projeto/Dev`:

```powershell
python -X utf8 scripts/prepare_full_catalogue.py
```

O gerador verifica a qualidade e o SHA-256 do CSV original e cria:

- `postgresql/generated/full_catalogue.sql`: criação do esquema e carregamento numa única transação.
- `postgresql/generated/full_catalogue_manifest.json`: contagens previstas, hashes e convenção dos IDs.

Os oito IDs locais da amostra são preservados. Os restantes são atribuídos por ordenação do `source_id`; mantêm-se para esta fonte inalterada, mas podem mudar se o catálogo mudar. `source_id` continua a ser a referência de proveniência.

Campos numéricos vazios tornam-se `NULL`. As contagens são convertidas com aritmética decimal exata, sem truncar frações. As etiquetas são separadas por vírgulas, aparadas e deduplicadas apenas dentro do mesmo estabelecimento, como na amostra. Nenhum registo é fundido apenas pelo nome.

## 2. Carregar e verificar numa instância isolada

```powershell
python -X utf8 scripts/check_full_catalogue.py
```

Requer Python 3 e PostgreSQL 16. O script gera o SQL, cria uma instância nova numa pasta temporária fora do OneDrive, carrega os dados, compara todos os valores e etiquetas com a fonte e para o servidor no fim. Não contacta nem apaga bases de trabalho existentes. A pasta do cluster fica no disco para inspeção; o seu caminho é registado no relatório.

Os testes incluem preservação dos IDs da amostra, ausência de alterações nos ficheiros de origem, literais com acentos e apóstrofos, recusa de um segundo carregamento sobre o mesmo esquema e reversão da criação e dos dados quando o carregamento falha. O teste de falha usa outra base descartável da mesma instância isolada.

Se a porta estiver ocupada, a execução recusa avançar. Para um teste separado, usar `--port 55442`. Para outra instalação PostgreSQL, usar `--pg-bin 'C:\Program Files\PostgreSQL\16\bin'`.

Resultados da execução:

- `results/full_catalogue_setup.txt`: registo do carregamento normal.
- `results/full_catalogue_validation.json`: data real da execução, contagens, verificações, caminho do cluster e estado final do servidor.

Um relatório anterior não prova que a execução atual passou: confirmar o código de saída, a data e `status`. Uma falha antes de criar a instância pode não produzir um novo relatório.

## 3. Abrir para trabalhar

Para abrir o catálogo com o cenário sintético:

```powershell
python -X utf8 scripts/check_full_catalogue.py --with-activity --keep-open
```

Esperar pela mensagem `Base aberta` e manter esse terminal aberto. Num segundo terminal na mesma pasta:

```powershell
npm run studio:p1
```

Abrir o endereço indicado pelo Prisma Studio, selecionar o schema `tiago_lab` e a tabela `establishment` ou `establishment_label`. O Studio da P1 usa a porta 5556 e a ligação fixa à porta PostgreSQL 55441; se escolheres outra porta PostgreSQL, essa ligação terá de ser adaptada.

Também é possível ligar pelo pgAdmin: host `127.0.0.1`, porta `55441`, base `tiago_p1`, utilizador `dmi_p1`, sem palavra-passe. A autenticação de confiança é apenas para esta instância local de treino, não para um serviço partilhado.

Fechar o Studio com Ctrl+C no segundo terminal e carregar Enter no primeiro para parar o servidor. Cada nova execução cria outra instância e reconstitui o catálogo: alterações manuais não são transportadas automaticamente. Guardar trabalho em scripts SQL, não apenas na interface.

## Importação manual e limites

Para uma base nova escolhida explicitamente por ti, abrir e executar `generated/full_catalogue.sql` completo no cliente PostgreSQL. Esse ficheiro já inclui o esquema: não executar antes `01_schema.sql`. O segundo carregamento no mesmo esquema é recusado, não apaga nem substitui dados existentes.

Não executar `02_sample_data.sql` sobre o catálogo completo: contém os mesmos oito estabelecimentos e causaria conflitos. Os resultados esperados anotados em `03_queries.sql` são os da pequena amostra, não os do catálogo completo. Nesta etapa sem atividade, as contagens de visitas são zero.

A fonte XML/BaseX não é alterada nem carregada por estes scripts. No modo com atividade, os identificadores culturais e os hashes são verificados lendo o XML; não se implementa aqui a integração virtual da P2.

## 4. Gerar e verificar a atividade separadamente

```powershell
python -X utf8 scripts/prepare_synthetic_activity.py
python -X utf8 scripts/check_full_catalogue.py --with-activity
```

O primeiro comando só gera ficheiros; o segundo cria outra instância de teste, carrega catálogo e atividade e verifica os resultados. A definição e os limites estão no [cenário sintético](../models/05_cenario_sintetico_p1.md). A data de referência é 21/10/2026 e não a data atual.

Em importação manual, executar `generated/full_catalogue.sql` numa base nova e, só depois, `generated/synthetic_activity.sql`. São duas transações separadas: um erro na atividade não remove o catálogo já carregado. A atividade exige tabelas vazias e recusa um segundo carregamento.

O modo com atividade produz `results/p1_activity_validation.json`, `results/p1_activity_setup.txt` e `results/p1_activity_queries.json`, mantendo o relatório do modo sem atividade separado. As consultas estão em `06_p1_activity_queries.sql`; a demonstração com atividade passou 37 verificações em 02/11/2026.
