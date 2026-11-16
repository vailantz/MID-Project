# Catálogos culturais municipais

`79922_2.xml` é a representação cultural usada na proposta aceite: 67 registos de museus e 63 de monumentos. Preserva identificadores, descrições, contactos, coordenadas e proveniência. É uma transformação produzida para o projeto; não é apresentado como o formato original publicado pela Câmara.

O desenvolvimento atual consulta uma cópia de trabalho em `../../Dev/data/cultural_catalogue.xml`. A existência das duas cópias pequenas é intencional: esta conserva a fonte aceite e a outra pode evoluir durante o desenvolvimento.

## Origens

- [Museus](https://dados.cm-lisboa.pt/dataset/museus): serviço ArcGIS `EquipamentosCulturais`, layer 3.
- [Monumentos Nacionais](https://dados.cm-lisboa.pt/dataset/monumentos-nacionais): serviço ArcGIS `Patrimonio`, layer 12.
- Acesso registado na proposta: 14/10/2026. Os catálogos municipais indicam CC0.

## Ficheiros recebidos inicialmente

A subpasta `recebidos_colega` conserva `79922_1.sqlite` e `79922_2.geojson`, recebidos com a proposta inicial do colega. São materiais de origem da preparação do projeto e não definem as tecnologias atuais. Não se afirma que ambos foram descarregados nesses formatos diretamente do portal municipal.

O catálogo não contém pessoas, reservas, entradas vendidas ou visitas individuais reais. As visitas culturais do nosso cenário são sintéticas e ficam em PostgreSQL, referindo os IDs do XML.
