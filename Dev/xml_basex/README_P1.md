# XML/BaseX — fonte cultural da P1

Preparada e verificada em **2 de novembro de 2026**. Responsável: Tiago. Esta é a segunda fonte local do Tiago; não é ainda a integração virtual completa da P2 nem o relatório P1 final.

## Dados e proveniência

O catálogo tem **130 registos: 67 museus e 63 monumentos**. O XML aceite é uma transformação preparada para o projeto a partir dos dados municipais, não o formato original publicado pelo portal. A proveniência detalhada está em `../../Fontes/Camara_Municipal/README.md`.

- Original aceite: `../../Fontes/Camara_Municipal/79922_2.xml`.
- Cópia de trabalho: `../data/cultural_catalogue.xml`, preservada byte a byte nesta preparação.
- Acesso registado às fontes: 14/10/2026; `generatedOn` do XML: 15/10/2026. Estas datas não são atualizadas ao executar os testes.
- Pessoas, reservas e visitas não são inseridas no catálogo cultural. A atividade fictícia continua em PostgreSQL.

Os nomes repetidos não são fundidos automaticamente. Os 130 registos não demonstram 130 locais físicos diferentes, nem se afirma que todos continuam abertos ou com contactos atuais.

## Preparar e verificar

Num terminal em `Projeto/Dev`:

```powershell
python -X utf8 scripts/check_basex_p1.py
```

Ambiente usado: Python com `lxml`, Java 17 e o JAR BaseX 12.4 já preservado em `tools/BaseX124.jar`. Não é necessário iniciar PostgreSQL para esta verificação.

O script valida hashes e XSD, cria a base **`tiago_culture_p1`** com o documento `catalogue.xml`, executa as consultas e guarda os resultados. A configuração e os dados ficam em `.runtime/basex_p1`, separados de `.runtime/basex` e da base de aula `tiago_culture_lab`.

A verificação pode demorar enquanto inicia várias chamadas Java e testa cópias do catálogo. O script mostra mensagens de progresso e termina com `PASS` se todas as verificações passarem. Não iniciar outra cópia do comando enquanto a primeira ainda estiver a correr.

Se a base P1 já existir, o programa compara todo o conteúdo com o XML de referência antes de a reutilizar. Uma divergência é assinalada: não é corrigida apagando ou substituindo a base. Para um teste com outro estado, escolher uma subpasta nova de `.runtime` através de `--state`; o lançador abaixo continua a usar apenas o estado P1 por omissão.

As chamadas BaseX terminam no fim de cada comando, mas a base fica no disco. Não é preciso manter um servidor ou um terminal de verificação aberto para consultar esta base local.

## Consultar a base preparada

Em PowerShell, na pasta `Projeto/Dev`:

```powershell
.\scripts\basex_p1.ps1 -i tiago_culture_p1 -Q .\xml_basex\01_museums.xq
.\scripts\basex_p1.ps1 -i tiago_culture_p1 -Q .\xml_basex\02_counts.xq
.\scripts\basex_p1.ps1 -i tiago_culture_p1 -Q .\xml_basex\05_contactable_places.xq
.\scripts\basex_p1.ps1 -i tiago_culture_p1 -Q .\xml_basex\06_p1_quality.xq
```

O lançador recusa uma configuração cujo `DBPATH` não corresponda à pasta reservada para a P1. Não abre a base global do utilizador nem a da aula.

## Consultas e resultados esperados

- **`01_museums.xq` — simples:** lista os 67 museus, por nome, preservando os IDs. Responde à procura de oferta cultural de uma categoria.
- **`02_counts.xq` — intermédia:** agrega registos por categoria: 67 museus e 63 monumentos. Não conta visitas ou visitantes.
- **`03_cultural_interface.xq` — interface:** devolve ID, categoria, nome e coordenadas dos 130 registos. Não é, por si só, uma integração com PostgreSQL.
- **`04_quality.xq` — qualidade básica:** verifica IDs duplicados, nomes ausentes, categorias desconhecidas, referências de origem e coordenadas não convertíveis.
- **`05_contactable_places.xq` — complexa neste exercício:** relaciona cada lugar com a sua origem, seleciona os que têm descrição e pelo menos telefone, email ou website utilizável e constrói o resultado com contactos e proveniência. Devolve **76 registos**.
- **`06_p1_quality.xq` — qualidade complementar:** verifica coerência de categoria, origem e prefixo do ID; descreve ausências e nomes repetidos.

As dificuldades são propostas justificadas pelas operações das consultas. A escolha das duas consultas individuais finais e das oito consultas entre subtemas deve continuar a ser coordenada com o Gonçalo.

Um contacto utilizável nesta consulta é apenas um elemento não nulo, não vazio e diferente de `-`. Não foi verificada a validade de telefones, emails, URLs ou a disponibilidade de websites. A consulta normaliza espaços na apresentação, mas não inventa contactos nem acrescenta protocolos aos websites.

## Resultados de qualidade observados

- Telefone: 73 valores preenchidos, 57 nulos explícitos.
- Email e website: 71 valores preenchidos e 59 nulos explícitos em cada campo.
- Fax: ausente em 63 registos e nulo explícito nos outros 67.
- Descrição: 127 preenchidas e três nulas explícitas.
- Quatro nomes ocorrem duas vezes: Palácio Fronteira, Museu Nacional dos Coches, Museu de Lisboa - Palácio Pimenta e Palácio Nacional da Ajuda. Os registos mantêm IDs distintos.
- Não foram encontrados bloqueios nas regras estruturais e semânticas verificadas. Isso não prova atualidade, correção factual ou localização dentro de uma fronteira municipal.

## XSD, verificações e limites

`catalogue.xsd` é o esquema XSD 1.0 definido pelo projeto. Valida estrutura comum, nomes não vazios, categorias, tipos, intervalos de coordenadas, identidade e referências de origem. Os campos brutos de `sourceFields` são preservados sem validação específica de cada campo.

A validação XSD é executada pelo verificador Python antes da preparação da base; não é uma restrição automaticamente reaplicada a futuras alterações manuais em BaseX. Algumas regras entre atributos, como a concordância entre categoria e prefixo do ID, são verificadas separadamente pela consulta de qualidade.

Passaram **36 verificações** na execução de 02/11/2026: resultados completos comparados com o XML, dez alterações inválidas rejeitadas pelo XSD, duas incoerências aceites pelo XSD mas detetadas por XQuery, criação/reutilização e deteção de uma base alterada sem a substituir. As alterações de teste são feitas em cópias, não na fonte ou na base P1 principal.

Também foram verificadas as sete referências culturais do cenário sintético contra os registos efetivamente devolvidos por BaseX. Este teste lê o JSON do cenário; não executa consultas PostgreSQL nem implementa um mediador entre as duas bases.

Resultados em `../results/basex_p1/validation.json` e nos seis XML dessa pasta. O relatório regista as datas reais de execução, o estado, os hashes e os limites. A pasta `.runtime` é recriável; não é preciso entregá-la como substituto dos scripts e fontes.

O modelo e as decisões para o relatório estão em `../models/06_xml_basex_p1.md`. Preparado com apoio de Codex/ChatGPT; Tiago deve rever as decisões e compreender as consultas antes de as defender.
