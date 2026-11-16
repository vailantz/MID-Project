# Modelo da fonte cultural XML/BaseX — P1

Revisão de **2 de novembro de 2026**. Responsável: Tiago. Documento de trabalho, não relatório final nem validação por stakeholders.

## Necessidades e escolha da tecnologia

- **RC1:** encontrar oferta cultural por categoria, distinguindo museus e monumentos.
- **RC2:** resumir a cobertura do catálogo por categoria.
- **RC3:** encontrar registos com descrição e contactos preenchidos, indicando a origem da informação.
- **RC4:** disponibilizar identificadores estáveis na fonte para que visitas fictícias em PostgreSQL possam referir destinos culturais.

Estes requisitos derivam do protótipo e ainda não têm validação externa documentada. XML conserva a estrutura hierárquica de localização e contactos e os campos específicos de cada origem; BaseX permite consultar essa estrutura com XQuery sem a transformar numa tabela PostgreSQL. A escolha mantém esta fonte distinta da fonte relacional, sem acrescentar um terceiro sistema à parte do Tiago.

## Modelo conceptual

Uma origem de dados fornece vários registos de lugar cultural. Cada registo pertence a uma categoria e referencia uma origem. Tem nome, localização, contactos, descrição e campos brutos preservados. Um registo é uma entrada de catálogo, não uma visita nem necessariamente uma identidade física já resolvida.

As visitas pertencem ao cenário PostgreSQL e apontam para `place/@id`; o XML não passa a conter pessoas ou eventos para justificar a ligação. A regra de que o destino externo existe tem de ser verificada fora das chaves estrangeiras PostgreSQL.

## Modelo lógico XML

- **`culturalCatalogue`:** raiz, com data de geração e sistema de coordenadas `EPSG:4326`.
- **`sources/source`:** metadados de cada origem: ID, fornecedor, data de acesso, endereço do catálogo e licença declarada. As duas origens são identificadas por `museum` e `monument`.
- **`place`:** ID único no documento, categoria e `sourceRef`. Atributos descrevem identidade, classificação e proveniência, não nomes de tabelas SQL.
- **`place/name`:** nome obrigatório e não vazio; não é uma chave de identidade.
- **`place/location`:** morada, latitude, longitude e freguesia opcional. O catálogo tem campos de freguesia nos monumentos e não nos museus; não foram preenchidos artificialmente.
- **`place/contact`:** telefone, email, website e fax opcional. Elementos nulos explícitos, elementos ausentes e textos vazios são situações distintas.
- **`place/description`:** descrição textual, admitindo nulo explícito.
- **`place/sourceFields`:** campos brutos específicos da origem, preservados sem impor uma estrutura única a museus e monumentos.

O XSD exige pelo menos uma origem e um lugar, e impõe chaves para os IDs de origem e de lugar e uma referência de `place/@sourceRef` à origem existente. Nesta instância há duas origens e 130 registos.

Os IDs têm prefixo `museum:` ou `monument:` e identificador preservado da preparação da fonte. Não são substituídos pelos nomes. A concordância entre prefixo, categoria e origem é uma regra semântica verificada em XQuery, adicional à forma de ID admitida pelo XSD 1.0.

## Modelo físico e execução

- Tecnologia instalada no projeto: BaseX 12.4, JAR local com SHA-256 verificado.
- Base P1: `tiago_culture_p1`; recurso XML: `catalogue.xml`.
- Estado e configuração locais: `Dev/.runtime/basex_p1`; a base de aula usa outro estado e outro nome.
- Fonte aceite e cópia de trabalho mantêm o mesmo SHA-256; a base é comparada com a árvore XML de referência antes de ser reutilizada.
- O XSD é aplicado pelo carregador/verificador, não por uma restrição permanente do motor. As coordenadas XML são conteúdo textual validado como decimal; a interface e os testes não confundem ordenação textual com comparação numérica.
- Não há processo servidor mantido por este fluxo: cada chamada CLI abre a base local e termina. Os dados persistem no disco.

Não se altera a fonte para normalizar contactos ou resolver potenciais duplicados. As consultas de apresentação normalizam espaços, preservando a fonte e os campos brutos.

## Qualidade, heterogeneidade e ligação futura

Existem 67 museus e 63 monumentos. Contactos e descrições podem ser nulos; fax pode estar ausente. Quatro nomes repetidos não foram usados para fundir identidades. O relatório detalhado encontra-se em `../results/basex_p1/validation.json`.

Há heterogeneidade estrutural entre XML hierárquico e relações SQL, sintática entre IDs textuais externos e IDs inteiros locais, e semântica entre um lugar de catálogo, um evento de visita e uma presença acumulada. A descrição de um museu não demonstra que uma pessoa o visitou; essa atividade é fictícia e está noutra fonte.

As sete visitas culturais do cenário P1 resolvem para IDs presentes na base BaseX preparada. Isso confirma as referências do cenário atual, não uma identidade comum com utilizadores das fontes do Gonçalo nem uma integração virtual completa. O desenho do esquema global e das consultas entre subtemas continua a ser trabalho a coordenar para a P2.

## Estado para a entrega

A fonte está implementada, povoada e verificada, com XSD, consultas e guia reproduzível em `../xml_basex/README_P1.md`. Passaram 36 verificações próprias nesta preparação. Ainda é necessário selecionar as consultas finais do grupo, consolidar requisitos, modelos e limitações no relatório P1 e rever a declaração de contribuições.

Texto preparado com apoio de Codex/ChatGPT. Não declara aprovação académica nem consulta a especialistas de domínio que não tenha ocorrido.
