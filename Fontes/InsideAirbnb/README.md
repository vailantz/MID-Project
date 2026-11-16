# Fontes de alojamento do Gonçalo

- `MemberA2.json`: 25 020 documentos de alojamentos, preparados para MongoDB.
- `reviews.zip`: contém `reviews.csv`, com 1 950 076 reviews. A fonte de conteúdo não estruturado corresponde ao texto da coluna `comments`; IDs e datas dão contexto a esse texto.

Referência da proposta: [Inside Airbnb — Lisboa](https://insideairbnb.com/get-the-data/#lisbon), snapshot de 19/09/2026, licença CC BY 4.0.

O JSON foi preparado a partir de dados publicados em CSV; não é apresentado como o formato original do download. O CSV das reviews está apenas embalado em ZIP. Os nomes e conteúdos recebidos para a proposta aceite foram preservados.

Foram eliminadas as cópias redundantes que estavam em `Proposta1` e no ZIP completo da proposta. Os CSV internos dos dois antigos `reviews.zip` foram comparados por SHA-256 e eram idênticos, apesar de a embalagem ZIP ser diferente.

Esta pasta guarda uma cópia de referência das fontes do colega para a integração; a implementação da parte dele continua a ser da sua responsabilidade.
