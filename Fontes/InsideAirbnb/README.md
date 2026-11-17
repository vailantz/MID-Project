# Fontes de alojamento do Gonçalo

Os originais utilizados na implementação A1/A2 estão em
[`z_Code/data/original/`](../../z_Code/data/original/):

- `79189_1.csv`: 1 950 076 reviews; o texto da coluna `comments` constitui o
  conteúdo não estruturado, acompanhado pelos identificadores e datas da fonte.
- `79189_2.json`: extrato de 25 020 alojamentos, preparado a partir dos CSV
  publicados pela Inside Airbnb; não representa o formato original do download.

Os scripts em [`z_Code/`](../../z_Code/) geram os dados de exercício e preparam
as fontes MongoDB e Elasticsearch. Os vetores concluídos das reviews estão em
[`z_Code/data/embeddings/`](../../z_Code/data/embeddings/). Os originais e os
vetores são distribuidos com Git LFS: executar `git lfs pull` após clonar.

Fonte: [Inside Airbnb - Lisboa](https://insideairbnb.com/get-the-data/#lisbon),
snapshot de 19/09/2026, licença CC BY 4.0; extratos recebidos em 14/10/2026.
